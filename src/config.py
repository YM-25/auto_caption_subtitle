"""
Central configuration for AutoCaption Pro.

All tunable settings (paths, model, cleanup, secrets) live here.
Override via environment variables where noted.
"""

import os

# -----------------------------------------------------------------------------
# Paths (relative to project root)
# -----------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_data_paths(base_dir=None):
    """Return dict of data folder paths. Use base_dir for tests or overrides."""
    root = base_dir if base_dir is not None else BASE_DIR
    return {
        "videos": os.path.join(root, "data", "videos"),
        "audios": os.path.join(root, "data", "audios"),
        "transcripts": os.path.join(root, "data", "transcripts"),
    }


# -----------------------------------------------------------------------------
# Whisper model (balance of speed vs accuracy)
# Options: tiny, base, small, medium, large, large-v2, large-v3
# -----------------------------------------------------------------------------
WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "base").strip() or "base"


# -----------------------------------------------------------------------------
# Cleanup: delete uploaded video and extracted audio after successful processing?
# Set CLEANUP_AFTER_PROCESS=1 to enable (saves disk; re-processing re-extracts).
# -----------------------------------------------------------------------------
CLEANUP_AFTER_PROCESS = os.environ.get("CLEANUP_AFTER_PROCESS", "").lower() in ("1", "true", "yes")


# -----------------------------------------------------------------------------
# Language codes: canonical form for comparison (Whisper returns e.g. "en", "zh";
# UI may send "en", "zh-CN"). We normalize to primary code for "same language" check.
# -----------------------------------------------------------------------------
def normalize_lang_code(code):
    """Return a canonical language code for comparison (e.g. 'zh-CN' -> 'zh', 'en' -> 'en')."""
    if not code:
        return ""
    code = (code or "").strip().lower()
    # Map common variants to primary code
    if code.startswith("zh"):
        if "hant" in code or code.endswith("-tw") or code.endswith("-hk") or code.endswith("-mo"):
            return "zh-tw"
        if "hans" in code or code.endswith("-cn") or code.endswith("-sg"):
            return "zh-cn"
        return "zh"
    if code.startswith("en"):
        return "en"
    # Return first part of code (e.g. "ja" from "ja-JP") or full if no hyphen
    return code.split("-")[0] if "-" in code else code


# -----------------------------------------------------------------------------
# Flask / app (used by app.py)
# -----------------------------------------------------------------------------
def get_secret_key():
    """Secret key for Flask session. Use FLASK_SECRET_KEY in production."""
    return os.environ.get("FLASK_SECRET_KEY") or os.environ.get("SECRET_KEY") or None


ALLOWED_VIDEO_EXTENSIONS = {"mp4", "avi", "mov", "mkv"}
MAX_UPLOAD_MB = 500
