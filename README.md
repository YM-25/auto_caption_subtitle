<div align="center">
  <h1>AutoCaption Pro 🎥📝</h1>
  <p><em>Vibe your subtitles like vibing code.</em></p>
  <p><strong>English</strong> | <a href="readme_chn.md">中文</a></p>
</div>

---

**AutoCaption Pro** is an intelligent, web-based tool designed to automatically generate, translate, and synchronize subtitles for your videos. It leverages a powerful hybrid architecture:
- **Local Intelligence**: Uses OpenAI's **Whisper** model for state-of-the-art speech recognition, running directly on your hardware for privacy and speed.
- **Cloud Translation (Optional)**: Supports high-quality translation via **Google Gemini** and **OpenAI ChatGPT** with your own API keys, or lightweight translation using **Deep Translator**.


## ✨ Features

- **🚀 Batch Video Upload**: Upload multiple videos at once and process them in a queue.
- **🎙️ Automatic Transcription**: Converts video speech to text with high accuracy using Whisper.
- **🌍 Smart Hybrid Translation**:
  - **Local/Cloud**: Choose between local `deep-translator` or superior cloud-based LLMs (**Gemini 3 Flash/Pro**, **GPT-5/5.2**).
  - **Dynamic Workflow**: English audio is smartly translated to **Chinese (Simplified)**, while other languages default to **English (UK / en-GB)**.
  - **Precision Controls**: Native support for **Chinese Simplified/Traditional** and language-specific overrides.
- **🤖 Integrated AI Services**:
  - **API Key Management**: Securely input and verify Gemini/GPT keys directly in the browser.
  - **AI Prompt Expansion**: Use LLMs to automatically refine and expand transcription prompts based on context.
  - **LLM Translation**: Use world-class LLMs to interpret nuances, slang, and technical terms.
- **⚡ Sequential Batch Processing**: Processes videos one by one with individual progress tracking.
- **📥 Multiple Export Formats**:
  - `*.{source}.srt`: Original language subtitles (e.g. `.zh-cn`).
  - `*.{source}__{target}.srt`: Translated subtitles (e.g. `.zh-cn__en-gb`).
  - `*.{source}__{target}.dual.srt`: **Bilingual subtitles** (Target on top, Source on bottom).
- **🧾 SRT Translate Mode**: Upload edited SRT files and generate translated + bilingual outputs.
- **📚 Glossary Manager**: Save reusable glossary terms, upload MD/TXT/JSON glossaries, and append per-video terms.
- **🧠 Filename Keyword Inference**: Auto-infer keywords from filenames to bias transcription prompts.
- **🧹 History Management**: Cleanly wipes uploaded files and generated transcripts.
- **⏸️ Queue Controls**: Pause/resume batch processing, retry failed items, and move items to the top.
- **🧾 Processing Logs**: Auto-saved JSON logs per job with preview/download in the UI.
- **🎨 Premium Wide UI**: A modern, 1080px wide horizontal interface for efficient batch work.
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
2. **Configure AI (Optional)**: Go to the **AI & Glossary Configuration** section to set your Gemini or GPT API key. Verify the key to unlock high-quality translation.
3. **Set Languages**: Configure **Source** and **Target** languages for each video in the horizontal list.
4. **Advanced Settings**: Choose a Whisper model and initial prompt. Enable **Auto-expand prompt using AI** for better accuracy.
5. **Process**: Click **Generate All Subtitles**.
6. **Download**: Once a video is done, use the **Get Files** dropdown to download SRT files.
7. **Clear History**: Removes all uploaded videos, extracted audios, and generated transcripts to free up disk space.

### SRT Translate

1. Switch to the **SRT Translate** tab.
2. Upload one or more `.srt` files.
3. Choose source/target languages and run **Translate SRT Files**.
4. Download the translated and dual subtitles from **Get Files**.

For SRT Translate, if a cue has two lines, the system always treats the **second line** as the source text and regenerates all outputs accordingly. When the source language is set to **Auto**, it uses lightweight script detection to pick a sensible default (e.g. Latin → English, Han → Chinese).

### Glossary

Use the **Glossary** panel to keep terminology consistent across runs.

- **Saved glossary** is stored at `data/glossary.json` and can be previewed/downloaded from the UI.
- **Input + file upload** supports `term = translation` or `term -> translation` (one per line) and JSON glossary lists.
- **Per-video glossary** can be appended and optionally saved to the global glossary.
- **Infer terms from filename** adds keywords to the Whisper prompt for better transcription of names or topics.


## 📂 Project Structure

```
auto_caption_subtitle/
├── app.py                 # Flask app; dependency check runs only when started here
├── .env.example           # Optional env vars (copy to .env)
├── requirements.txt      # Python dependencies
├── src/
│   ├── config.py         # Central config: paths, Whisper model, cleanup, secret
│   ├── dependency_manager.py  # Check/install deps (invoked at app startup)
│   ├── glossary.py        # Glossary load/save/parse helpers
│   ├── pipeline.py       # Video → audio → transcribe → translate → SRT
│   ├── srt_utils.py       # SRT parsing + language hints
│   ├── transcriber.py    # Whisper & SRT save helpers
│   ├── translator.py     # Segment translation (deep-translator)
│   └── video_processor.py    # FFmpeg video → audio
├── templates/
│   └── index.html        # Main UI
├── static/
│   ├── css/style.css     # Styles
│   └── js/script.js      # Upload, NDJSON stream, progress, downloads
└── data/                 # Auto-created; videos, audios, transcripts (git-ignored)
  ├── glossary.json     # Saved glossary terms
  └── transcripts/      # Subtitle outputs + JSON logs
```

## 📝 License

[MIT License](LICENSE)
