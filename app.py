"""
AutoCaption Pro — Flask application entry point.

Dependency check runs only when starting the server (python app.py).
Configuration is centralized in src.config. Optional .env is loaded if present.
"""

import os

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

from flask import Flask, render_template, request, send_file, jsonify, Response, stream_with_context
from werkzeug.utils import secure_filename

from src.config import (
    get_data_paths,
    get_secret_key,
    ALLOWED_VIDEO_EXTENSIONS,
    MAX_UPLOAD_MB,
    CLEANUP_AFTER_PROCESS,
)
from src.pipeline import process_video, process_srt

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

    filename = secure_filename(file.filename)
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


    def to_download_path(file_path):
        rel_path = os.path.relpath(file_path, TRANSCRIPT_FOLDER)
        return rel_path.replace(os.sep, "/")

    def generate():
        try:
            yield json.dumps({"type": "progress", "message": f"File uploaded: {filename}"}) + "\n"

            q = queue.Queue()

            def worker():
                try:
                    def cb(msg):
                        q.put({"type": "progress", "message": msg})

                    outputs = process_video(
                        save_path,
                        source_lang=source_lang,
                        target_lang=target_lang,
                        model_name=whisper_model,
                        initial_prompt=whisper_prompt,
                        progress_callback=cb,
                    )

                    result_files = []
                    if "original" in outputs:
                        result_files.append({
                            "label": "Original Subtitles (.srt)",
                            "url": f"/download/{to_download_path(outputs['original'])}",
                        })
                    if "translated" in outputs:
                        result_files.append({
                            "label": "Translated Subtitles (.srt)",
                            "url": f"/download/{to_download_path(outputs['translated'])}",
                        })
                    if "dual" in outputs:
                        result_files.append({
                            "label": "Bilingual Subtitles (Dual .srt)",
                            "url": f"/download/{to_download_path(outputs['dual'])}",
                        })

                    q.put({"type": "result", "files": result_files})
                except Exception as e:
                    q.put({"type": "error", "message": str(e)})
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

    filename = secure_filename(file.filename)
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

    def to_download_path(file_path):
        rel_path = os.path.relpath(file_path, TRANSCRIPT_FOLDER)
        return rel_path.replace(os.sep, "/")

    def generate():
        try:
            yield json.dumps({"type": "progress", "message": f"SRT uploaded: {filename}"}) + "\n"

            q = queue.Queue()

            def worker():
                try:
                    def cb(msg):
                        q.put({"type": "progress", "message": msg})

                    outputs = process_srt(
                        save_path,
                        source_lang=source_lang,
                        target_lang=target_lang,
                        progress_callback=cb,
                    )

                    result_files = []
                    if "original" in outputs:
                        result_files.append({
                            "label": "Original Subtitles (.srt)",
                            "url": f"/download/{to_download_path(outputs['original'])}",
                        })
                    if "translated" in outputs:
                        result_files.append({
                            "label": "Translated Subtitles (.srt)",
                            "url": f"/download/{to_download_path(outputs['translated'])}",
                        })
                    if "dual" in outputs:
                        result_files.append({
                            "label": "Bilingual Subtitles (Dual .srt)",
                            "url": f"/download/{to_download_path(outputs['dual'])}",
                        })

                    q.put({"type": "result", "files": result_files})
                except Exception as e:
                    q.put({"type": "error", "message": str(e)})
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
# Entry point: run dependency check once, then start server
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    from src.dependency_manager import check_and_install_dependencies
    check_and_install_dependencies()

    debug = os.environ.get("FLASK_DEBUG", "0").lower() in ("1", "true", "yes")
    port = int(os.environ.get("PORT", "5000"))
    app.run(debug=debug, port=port)
