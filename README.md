<div align="center">
  <h1>AutoCaption Pro 🎥📝</h1>
  <p><em>Vibe your subtitles like vibing code.</em></p>
  <p><strong>English</strong> | 中文 (coming soon)</p>
</div>

---

**AutoCaption Pro** is an intelligent, web-based tool designed to automatically generate, translate, and synchronize subtitles for your videos. Powered by OpenAI's **Whisper** model for state-of-the-art speech recognition and **Deep Translator** for multilingual support.

This tool runs fully **locally**. You need a local Python installation and required packages.


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
- **🧾 SRT Translate Mode**: Upload edited SRT files and generate translated + bilingual outputs.
- **🧹 History Management**: Cleanly wipes uploaded files and generated transcripts.
- **🎨 Premium Wide UI**: A modern, 1000px wide horizontal interface for efficient batch work.
- **🛠️ Auto-Dependency Check**: Automatically installs missing Python packages on startup.
- **🧪 Advanced Settings**: Optional Whisper model selection per batch.
- **📝 Per-Video Overrides**: You can override model and initial prompt per video.

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

2. **Install dependencies**:
  ```bash
  pip install -r requirements.txt
  ```

3. **Run the Application**:
   ```bash
   python app.py
   ```
   *The app will automatically check and install all required dependencies from `requirements.txt` on its first run.*

4. **Open your browser** and navigate to: `http://127.0.0.1:5000`

### Optional configuration

#### Virtual Environment (Recommended)

Create a virtual environment:
```bash
python -m venv .venv
```

Activate it:
- Windows: `.\.venv\Scripts\activate`
- macOS/Linux: `source .venv/bin/activate`

#### Environment Variables (.env)

Copy `.env.example` to `.env` and set variables as needed:

| Variable | Description |
|----------|-------------|
| `FLASK_SECRET_KEY` | Secret key for Flask (recommended in production). |
| `WHISPER_MODEL` | Whisper model: `tiny`, `base`, `small`, `medium`, `large` (default: `base`). |
| `CLEANUP_AFTER_PROCESS` | Set to `1` to delete uploaded video and extracted audio after successful processing. |
| `PORT` | Server port (default: `5000`). |
| `FLASK_DEBUG` | Set to `1` to enable debug mode. |

#### CUDA Acceleration (Optional)

To use CUDA acceleration, install a CUDA-enabled PyTorch build that matches your GPU/driver.
If you choose larger Whisper models (e.g. `medium`/`large`), GPU/CUDA is strongly recommended.
Note: `requirements.txt` installs the default CPU build of PyTorch unless you manually install a CUDA-enabled build.

## 🏃 Usage

1. **Upload**: Drag and drop multiple video files onto the upload area.
2. **Configure**: Set individual **Source** and **Target** languages for each video in the horizontal list (including Simplified/Traditional Chinese).
3. **Advanced (Optional)**: Choose a Whisper model and prompt for the batch; per-video overrides are available inside each item.
4. **Process**: Click **Generate All Subtitles**.
5. **Download**: Once a video is done, use the **Get Files** dropdown to download SRT files.
6. **Clear History**: Removes all uploaded videos, extracted audios, and generated transcripts from the server. Use when you want to free disk space or start fresh.

### SRT Translate

1. Switch to the **SRT Translate** tab.
2. Upload one or more `.srt` files.
3. Choose source/target languages and run **Translate SRT Files**.
4. Download the translated and dual subtitles from **Get Files**.

For SRT Translate, if a cue has two lines, the system always treats the **second line** as the source text and regenerates all outputs accordingly.


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
