# AutoCaption Pro 🎥📝

**AutoCaption Pro** is an intelligent, web-based tool designed to automatically generate, translate, and synchronize subtitles for your videos. Powered by OpenAI's **Whisper** model for state-of-the-art speech recognition and **Deep Translator** for multilingual support.


## ✨ Features

- **🚀 Batch Video Upload**: Upload multiple videos at once and process them in a queue.
- **🎙️ Automatic Transcription**: Converts video speech to text with high accuracy using Whisper.
- **🌍 Smart Translation**:
  - Automatically translates English to **Chinese (Simplified)**.
  - Translates other languages to **English (UK / en-GB)**.
  - If detected Chinese is ambiguous, defaults to **Simplified** for downstream logic.
  - Per-video language selection for customized results (including **Chinese Simplified/Traditional** and **None**).
- **⚡ Sequential Batch Processing**: Processes videos one by one with individual progress tracking.
- **📥 Multiple Export Formats**:
  - `*.{source}.srt`: Original language subtitles (e.g. `.zh-cn`).
  - `*.{source}__{target}.srt`: Translated subtitles (e.g. `.zh-cn__en-gb`).
  - `*.{source}__{target}.dual.srt`: **Bilingual subtitles** (Target on top, Source on bottom).
- **🧹 History Management**: Cleanly wipes uploaded files and generated transcripts.
- **🎨 Premium Wide UI**: A modern, 1000px wide horizontal interface for efficient batch work.
- **🛠️ Auto-Dependency Check**: Automatically installs missing Python packages on startup.
- **🧪 Advanced Settings**: Optional Whisper model selection per batch.

## 🚀 Getting Started

### Prerequisites
- **Python 3.8+**
- **FFmpeg**: Must be installed and added to your system PATH.
- **CUDA (Optional)**: Recommended for faster Whisper transcription (NVIDIA GPU).
- **Upload size limit**: Default max upload is **5 GB** (configurable in `src/config.py`).

### Installation & Run

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/auto_caption_subtitle.git
   cd auto_caption_subtitle
   ```

2. **Run the Application**:
   ```bash
   python app.py
   ```
   *The app will automatically check and install all required dependencies from `requirements.txt` on its first run.*

3. **Open your browser** and navigate to: `http://127.0.0.1:5000`

### Optional configuration

Copy `.env.example` to `.env` and set variables as needed:

| Variable | Description |
|----------|-------------|
| `FLASK_SECRET_KEY` | Secret key for Flask (recommended in production). |
| `WHISPER_MODEL` | Whisper model: `tiny`, `base`, `small`, `medium`, `large` (default: `base`). |
| `CLEANUP_AFTER_PROCESS` | Set to `1` to delete uploaded video and extracted audio after successful processing. |
| `PORT` | Server port (default: `5000`). |
| `FLASK_DEBUG` | Set to `1` to enable debug mode. |

## 🏃 Usage

1. **Upload**: Drag and drop multiple video files onto the upload area.
2. **Configure**: Set individual **Source** and **Target** languages for each video in the horizontal list (including Simplified/Traditional Chinese).
3. **Advanced (Optional)**: Choose a Whisper model to balance speed vs accuracy for the batch.
4. **Process**: Click **Generate All Subtitles**.
5. **Download**: Once a video is done, use the **Get Files** dropdown to download SRT files.
6. **Clear History**: Removes all uploaded videos, extracted audios, and generated transcripts from the server. Use when you want to free disk space or start fresh.


## 📂 Project Structure

```
auto_caption_subtitle/
├── app.py                 # Flask app; dependency check runs only when started here
├── .env.example           # Optional env vars (copy to .env)
├── requirements.txt      # Python dependencies
├── src/
│   ├── config.py         # Central config: paths, Whisper model, cleanup, secret
│   ├── dependency_manager.py  # Check/install deps (invoked at app startup)
│   ├── pipeline.py       # Video → audio → transcribe → translate → SRT
│   ├── transcriber.py    # Whisper & SRT save helpers
│   ├── translator.py     # Segment translation (deep-translator)
│   └── video_processor.py    # FFmpeg video → audio
├── templates/
│   └── index.html        # Main UI
├── static/
│   ├── css/style.css     # Styles
│   └── js/script.js      # Upload, NDJSON stream, progress, downloads
└── data/                 # Auto-created; videos, audios, transcripts (git-ignored)
```

## 📝 License

[MIT License](LICENSE)
