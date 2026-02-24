"""
AutoCaption Pro — Flask application entry point.

Dependency check runs only when starting the server (python app.py).
Configuration is centralized in src.config. Optional .env is loaded if present.
"""

import sys
import os

# 1. Run absolute first: ensure all required packages from requirements.txt are installed
if __name__ == "__main__":
    # Add project root to sys.path to ensure src imports work during dependency check if needed
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    try:
        from src.dependency_manager import check_and_install_dependencies
        check_and_install_dependencies()
    except Exception as e:
        print(f"Error during dependency check: {e}")

import re


# Load .env from project root so FLASK_SECRET_KEY, WHISPER_MODEL, etc. apply
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    pass
import json
import queue
import secrets
import shutil
import threading
import time
from datetime import datetime

from flask import Flask, render_template, request, send_file, jsonify, Response, stream_with_context

from src.config import (
    get_data_paths,
    get_secret_key,
    ALLOWED_VIDEO_EXTENSIONS,
    MAX_UPLOAD_MB,
    CLEANUP_AFTER_PROCESS,
    GLOSSARY_FILE,
)
from src.pipeline import process_video, process_srt
from src.glossary import (
    load_glossary,
    save_glossary,
    parse_glossary_text,
    parse_glossary_file,
    merge_glossaries,
    infer_glossary_from_filename,
)
from src.ai_service import verify_api_key

try:
    import torch
except Exception:
    torch = None

# -----------------------------------------------------------------------------
# App setup
# -----------------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = get_secret_key() or secrets.token_hex(16)

paths = get_data_paths()
UPLOAD_FOLDER = paths["videos"]
AUDIO_FOLDER = paths["audios"]
TRANSCRIPT_FOLDER = paths["transcripts"]

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["AUDIO_FOLDER"] = AUDIO_FOLDER
app.config["TRANSCRIPT_FOLDER"] = TRANSCRIPT_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024

for folder in (UPLOAD_FOLDER, AUDIO_FOLDER, TRANSCRIPT_FOLDER):
    os.makedirs(folder, exist_ok=True)


def allowed_file(filename):
    """Return True if filename has an allowed video extension."""
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_VIDEO_EXTENSIONS


def secure_filename_unicode(filename):
    """
    A Unicode-safe version of secure_filename.
    Preserves Chinese characters and other non-ASCII letters/numbers,
    while removing path separators and dangerous control characters.
    """
    if not filename:
        return "unnamed_file"
    
    # 1. Basic path normalization
    filename = os.path.basename(filename)
    
    # 2. Characters to strip/replace: 
    # Stop common injection chars like < > : " / \ | ? *
    # We allow underscores, hyphens, dots, and any non-control alphanumeric characters (including Chinese).
    bad_chars = r'[<>:"/\\|?*\x00-\x1f\x7f]'
    filename = re.sub(bad_chars, "_", filename)
    
    # 3. Trim leading/trailing whitespace and dots
    filename = filename.strip().strip(".")
    
    if not filename:
        return "unnamed_file"
    
    return filename


# -----------------------------------------------------------------------------
# Helpers for common route tasks
# -----------------------------------------------------------------------------
def handle_glossary_params(form_data, files_data, filename=None):
    """Common logic for merging glossaries from text, file, and saved json."""
    glossary_text = form_data.get("glossary_text", "").strip()
    glossary_use_saved = form_data.get("glossary_use_saved", "1").strip() == "1"
    glossary_save = form_data.get("glossary_save", "0").strip() == "1"
    glossary_use_filename = form_data.get("glossary_use_filename", "1").strip() == "1"
    glossary_save_text = form_data.get("glossary_save_text", "").strip()

    glossary_file = files_data.get("glossary_file")
    glossary_file_path = None
    if glossary_file and glossary_file.filename:
        glossary_name = secure_filename_unicode(glossary_file.filename)
        glossary_file_path = os.path.join(app.config["TRANSCRIPT_FOLDER"], f"glossary_{glossary_name}")
        glossary_file.save(glossary_file_path)

    saved_glossary = load_glossary(GLOSSARY_FILE) if glossary_use_saved else {}
    text_glossary = parse_glossary_text(glossary_text)
    file_glossary = parse_glossary_file(glossary_file_path) if glossary_file_path else {}
    merged_glossary = merge_glossaries(text_glossary, file_glossary, saved_glossary)

    if glossary_save and (text_glossary or file_glossary or glossary_save_text):
        save_text_glossary = parse_glossary_text(glossary_save_text)
        updated = merge_glossaries(saved_glossary, save_text_glossary, text_glossary, file_glossary)
        save_glossary(GLOSSARY_FILE, updated)

    return merged_glossary, glossary_use_filename


def build_whisper_prompt(initial_prompt, merged_glossary, filename, glossary_prompt_enabled, use_filename_enabled):
    """Enhance Whisper prompt with glossary terms and filename-inferred keywords."""
    prompt = initial_prompt or ""
    if glossary_prompt_enabled and merged_glossary:
        prompt_terms = ", ".join(sorted(merged_glossary.keys()))
        prompt = f"{prompt}\nGlossary terms: {prompt_terms}" if prompt else f"Glossary terms: {prompt_terms}"

    if use_filename_enabled and filename:
        inferred = infer_glossary_from_filename(filename)
        if inferred:
            inferred_terms = ", ".join(sorted(inferred.keys()))
            prompt = f"{prompt}\nTopic keywords: {inferred_terms}" if prompt else f"Topic keywords: {inferred_terms}"
    
    return prompt[:1000] if prompt else None


def save_processing_log(log_path, log_data):
    """Safely save log dictionary to JSON file."""
    try:
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(log_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Failed to save log: {e}")


def to_download_path(file_path):
    """Convert absolute file path to relative download URL path."""
    rel_path = os.path.relpath(file_path, TRANSCRIPT_FOLDER)
    return rel_path.replace(os.sep, "/")


def build_log_paths(base_name):
    """Build log file path and corresponding download/preview URLs."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"{base_name}.log.{timestamp}.json"
    log_path = os.path.join(TRANSCRIPT_FOLDER, log_filename)
    return log_path, f"/download/{to_download_path(log_path)}", f"/preview/{to_download_path(log_path)}"


# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/system_info")
def system_info():
    cuda_available = False
    if torch is not None:
        try:
            cuda_available = bool(torch.cuda.is_available())
        except Exception:
            cuda_available = False
    return jsonify({"cuda_available": cuda_available})


@app.route("/upload_and_process", methods=["POST"])
def upload_and_process():
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    if not (file and allowed_file(file.filename)):
        return jsonify({"error": "File type not allowed"}), 400

    filename = secure_filename_unicode(file.filename)
    save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(save_path)

    source_lang = request.form.get("source_language", "auto").strip() or None
    if source_lang == "auto":
        source_lang = None

    target_lang = request.form.get("target_language", "auto").strip()
    if target_lang == "auto":
        target_lang = "auto"
    elif not target_lang or target_lang == "none":
        target_lang = None

    whisper_model = request.form.get("whisper_model", "auto").strip()
    allowed_models = {"auto", "tiny", "base", "small", "medium", "large", "large-v2", "large-v3"}
    if whisper_model not in allowed_models:
        return jsonify({"error": "Invalid model selection"}), 400
    if whisper_model == "auto":
        whisper_model = None

    whisper_prompt = request.form.get("whisper_prompt", "").strip()
    if whisper_prompt:
        whisper_prompt = whisper_prompt[:1000]
    else:
        whisper_prompt = None

    merged_glossary, glossary_use_filename = handle_glossary_params(request.form, request.files, filename)
    glossary_prompt = request.form.get("glossary_prompt", "0").strip() == "1"
    whisper_prompt = build_whisper_prompt(
        request.form.get("whisper_prompt", "").strip(), 
        merged_glossary, 
        filename, 
        glossary_prompt, 
        glossary_use_filename
    )


    # AI Enhancement Parameters
    ai_provider = request.form.get("ai_provider", "gemini").strip()
    ai_model = request.form.get("ai_model", "").strip()
    ai_api_key = request.form.get("ai_api_key", "").strip()
    ai_enable_expansion = request.form.get("ai_enable_expansion", "0").strip() == "1"
    ai_enable_translation = request.form.get("ai_enable_translation", "0").strip() == "1"

    def generate():
        try:
            yield json.dumps({"type": "progress", "message": f"File uploaded: {filename}"}) + "\n"

            q = queue.Queue()

            log_data = {
                "filename": filename,
                "source_language": source_lang or "auto",
                "target_language": target_lang or "none",
                "whisper_model": whisper_model or "default",
                "whisper_prompt": whisper_prompt or "",
                "glossary_terms": sorted(list(merged_glossary.keys())),
                "status": "processing",
                "start_time": datetime.now().isoformat(),
                "events": [],
                "outputs": [],
                "error": None,
                "duration_sec": None,
            }
            start_ts = time.time()
            log_path, log_download_url, log_preview_url = build_log_paths(os.path.splitext(filename)[0])

            def worker():
                try:
                    def cb(payload):
                        if isinstance(payload, dict):
                            log_data["events"].append(payload)
                            q.put(payload)
                        else:
                            item = {"type": "progress", "message": payload}
                            log_data["events"].append(item)
                            q.put(item)

                    outputs = process_video(
                        save_path,
                        source_lang=source_lang,
                        target_lang=target_lang,
                        model_name=whisper_model,
                        initial_prompt=whisper_prompt,
                        glossary=merged_glossary,
                        progress_callback=cb,
                        ai_options={
                            "provider": ai_provider,
                            "model": ai_model,
                            "api_key": ai_api_key,
                            "enable_expansion": ai_enable_expansion,
                            "enable_translation": ai_enable_translation,
                        },
                    )

                    result_files = []
                    if "original" in outputs:
                        result_files.append({
                            "label": "Original Subtitles (.srt)",
                            "url": f"/download/{to_download_path(outputs['original'])}",
                        })
                        log_data["outputs"].append(outputs["original"])
                    if "translated" in outputs:
                        result_files.append({
                            "label": "Translated Subtitles (.srt)",
                            "url": f"/download/{to_download_path(outputs['translated'])}",
                        })
                        log_data["outputs"].append(outputs["translated"])
                    if "dual" in outputs:
                        result_files.append({
                            "label": "Bilingual Subtitles (Dual .srt)",
                            "url": f"/download/{to_download_path(outputs['dual'])}",
                        })
                        log_data["outputs"].append(outputs["dual"])

                    log_data["status"] = "completed"
                    log_data["duration_sec"] = round(time.time() - start_ts, 3)
                    log_data["end_time"] = datetime.now().isoformat()
                    save_processing_log(log_path, log_data)

                    q.put({
                        "type": "result",
                        "files": result_files,
                        "log": {"download_url": log_download_url, "preview_url": log_preview_url},
                    })
                except Exception as e:
                    log_data["status"] = "failed"
                    log_data["error"] = str(e)
                    log_data["duration_sec"] = round(time.time() - start_ts, 3)
                    log_data["end_time"] = datetime.now().isoformat()
                    save_processing_log(log_path, log_data)
                    q.put({
                        "type": "error",
                        "message": str(e),
                        "log": {"download_url": log_download_url, "preview_url": log_preview_url},
                    })
                finally:
                    q.put(None)

            t = threading.Thread(target=worker)
            t.start()

            while True:
                item = q.get()
                if item is None:
                    break
                yield json.dumps(item) + "\n"

            t.join()

            # Optional: delete uploaded video and extracted audio after success
            if CLEANUP_AFTER_PROCESS and os.path.isfile(save_path):
                try:
                    os.unlink(save_path)
                except OSError:
                    pass
                base_name = os.path.splitext(filename)[0]
                audio_path = os.path.join(app.config["AUDIO_FOLDER"], base_name + ".mp3")
                if os.path.isfile(audio_path):
                    try:
                        os.unlink(audio_path)
                    except OSError:
                        pass

        except Exception as e:
            yield json.dumps({"type": "error", "message": str(e)}) + "\n"

    return Response(stream_with_context(generate()), mimetype="application/x-ndjson")


@app.route("/upload_srt_and_translate", methods=["POST"])
def upload_srt_and_translate():
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    if not file.filename.lower().endswith(".srt"):
        return jsonify({"error": "File type not allowed"}), 400

    filename = secure_filename_unicode(file.filename)
    base_name = os.path.splitext(filename)[0]
    save_name = f"{base_name}.uploaded.srt"
    save_path = os.path.join(app.config["TRANSCRIPT_FOLDER"], save_name)
    file.save(save_path)

    source_lang = request.form.get("source_language", "auto").strip() or None
    if source_lang == "auto":
        source_lang = None

    target_lang = request.form.get("target_language", "auto").strip()
    if target_lang == "auto":
        target_lang = "auto"
    elif not target_lang or target_lang == "none":
        target_lang = None

    merged_glossary, _ = handle_glossary_params(request.form, request.files, filename)

    # AI Enhancement Parameters (capture before starting thread)
    ai_provider = request.form.get("ai_provider", "gemini").strip()
    ai_model = request.form.get("ai_model", "").strip()
    ai_api_key = request.form.get("ai_api_key", "").strip()
    ai_enable_translation = request.form.get("ai_enable_translation", "0").strip() == "1"

    def generate():
        try:
            yield json.dumps({"type": "progress", "message": f"SRT uploaded: {filename}"}) + "\n"

            q = queue.Queue()

            log_data = {
                "filename": filename,
                "source_language": source_lang or "auto",
                "target_language": target_lang or "none",
                "mode": "srt_translate",
                "glossary_terms": sorted(list(merged_glossary.keys())),
                "status": "processing",
                "start_time": datetime.now().isoformat(),
                "events": [],
                "outputs": [],
                "error": None,
                "duration_sec": None,
            }
            start_ts = time.time()
            log_path, log_download_url, log_preview_url = build_log_paths(base_name)

            def worker():
                try:
                    def cb(payload):
                        if isinstance(payload, dict):
                            log_data["events"].append(payload)
                            q.put(payload)
                        else:
                            item = {"type": "progress", "message": payload}
                            log_data["events"].append(item)
                            q.put(item)

                    outputs = process_srt(
                        save_path,
                        source_lang=source_lang,
                        target_lang=target_lang,
                        glossary=merged_glossary,
                        progress_callback=cb,
                        ai_options={
                            "provider": ai_provider,
                            "model": ai_model,
                            "api_key": ai_api_key,
                            "enable_translation": ai_enable_translation,
                        },
                    )

                    result_files = []
                    if "original" in outputs:
                        result_files.append({
                            "label": "Original Subtitles (.srt)",
                            "url": f"/download/{to_download_path(outputs['original'])}",
                        })
                        log_data["outputs"].append(outputs["original"])
                    if "translated" in outputs:
                        result_files.append({
                            "label": "Translated Subtitles (.srt)",
                            "url": f"/download/{to_download_path(outputs['translated'])}",
                        })
                        log_data["outputs"].append(outputs["translated"])
                    if "dual" in outputs:
                        result_files.append({
                            "label": "Bilingual Subtitles (Dual .srt)",
                            "url": f"/download/{to_download_path(outputs['dual'])}",
                        })
                        log_data["outputs"].append(outputs["dual"])

                    log_data["status"] = "completed"
                    log_data["duration_sec"] = round(time.time() - start_ts, 3)
                    log_data["end_time"] = datetime.now().isoformat()
                    save_processing_log(log_path, log_data)

                    q.put({
                        "type": "result",
                        "files": result_files,
                        "log": {"download_url": log_download_url, "preview_url": log_preview_url},
                    })
                except Exception as e:
                    log_data["status"] = "failed"
                    log_data["error"] = str(e)
                    log_data["duration_sec"] = round(time.time() - start_ts, 3)
                    log_data["end_time"] = datetime.now().isoformat()
                    save_processing_log(log_path, log_data)
                    q.put({
                        "type": "error",
                        "message": str(e),
                        "log": {"download_url": log_download_url, "preview_url": log_preview_url},
                    })
                finally:
                    q.put(None)

            t = threading.Thread(target=worker)
            t.start()

            while True:
                item = q.get()
                if item is None:
                    break
                yield json.dumps(item) + "\n"

            t.join()
        except Exception as e:
            yield json.dumps({"type": "error", "message": str(e)}) + "\n"

    return Response(stream_with_context(generate()), mimetype="application/x-ndjson")


@app.route("/download/<path:filename>")
def download_file(filename):
    root = os.path.abspath(app.config["TRANSCRIPT_FOLDER"])
    path = os.path.abspath(os.path.join(root, filename))
    if not path.startswith(root) or not os.path.isfile(path):
        return jsonify({"error": "File not found"}), 404
    return send_file(path, as_attachment=True, download_name=os.path.basename(path))


@app.route("/preview/<path:filename>")
def preview_file(filename):
    root = os.path.abspath(app.config["TRANSCRIPT_FOLDER"])
    path = os.path.abspath(os.path.join(root, filename))
    if not path.startswith(root) or not os.path.isfile(path):
        return jsonify({"error": "File not found"}), 404
    return send_file(path, as_attachment=False)


@app.route("/glossary/preview")
def preview_glossary():
    if not os.path.isfile(GLOSSARY_FILE):
        return jsonify({"error": "Glossary not found"}), 404
    return send_file(GLOSSARY_FILE, as_attachment=False)


@app.route("/glossary/download")
def download_glossary():
    if not os.path.isfile(GLOSSARY_FILE):
        return jsonify({"error": "Glossary not found"}), 404
    return send_file(GLOSSARY_FILE, as_attachment=True, download_name=os.path.basename(GLOSSARY_FILE))


@app.route("/glossary/save", methods=["POST"])
def save_glossary_now():
    glossary_text = request.form.get("glossary_text", "").strip()
    glossary_file = request.files.get("glossary_file")

    glossary_file_path = None
    if glossary_file and glossary_file.filename:
        glossary_name = secure_filename_unicode(glossary_file.filename)
        glossary_file_path = os.path.join(app.config["TRANSCRIPT_FOLDER"], f"glossary_{glossary_name}")
        glossary_file.save(glossary_file_path)

    saved_glossary = load_glossary(GLOSSARY_FILE)
    text_glossary = parse_glossary_text(glossary_text)
    file_glossary = parse_glossary_file(glossary_file_path) if glossary_file_path else {}

    merged = merge_glossaries(saved_glossary, text_glossary, file_glossary)
    save_glossary(GLOSSARY_FILE, merged)

    added_count = len(text_glossary) + len(file_glossary)
    return jsonify({"message": "Glossary saved", "total_terms": len(merged), "added_terms": added_count})


@app.route("/verify_api_key", methods=["POST"])
def verify_key():
    data = request.json or {}
    provider = data.get("provider")
    api_key = data.get("api_key")
    
    if not provider or not api_key:
        return jsonify({"success": False, "message": "Missing provider or API key."}), 400
        
    success, message = verify_api_key(provider, api_key)
    return jsonify({"success": success, "message": message})


@app.route("/clear_history", methods=["POST"])
def clear_history():
    """Remove all files in videos, audios, and transcripts folders."""
    try:
        for folder in (
            app.config["UPLOAD_FOLDER"],
            app.config["AUDIO_FOLDER"],
            app.config["TRANSCRIPT_FOLDER"],
        ):
            if not os.path.isdir(folder):
                continue
            for name in os.listdir(folder):
                path = os.path.join(folder, name)
                try:
                    if os.path.abspath(path) == os.path.abspath(GLOSSARY_FILE):
                        continue
                    if os.path.isfile(path) or os.path.islink(path):
                        os.unlink(path)
                    elif os.path.isdir(path):
                        shutil.rmtree(path)
                except OSError as e:
                    print(f"Failed to delete {path}: {e}")
        return jsonify({"message": "History cleared successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -----------------------------------------------------------------------------
# Entry point: run server
# -----------------------------------------------------------------------------
if __name__ == "__main__":

    debug = os.environ.get("FLASK_DEBUG", "0").lower() in ("1", "true", "yes")
    port = int(os.environ.get("PORT", "5000"))
    app.run(debug=debug, port=port)
