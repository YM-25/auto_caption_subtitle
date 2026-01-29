# AutoCaption Pro 🎥📝

**AutoCaption Pro** is an intelligent, web-based tool designed to automatically generate, translate, and synchronize subtitles for your videos. Powered by OpenAI's **Whisper** model for state-of-the-art speech recognition and **Deep Translator** for multilingual support.

![AutoCaption Pro Interface](https://via.placeholder.com/800x400?text=AutoCaption+Pro+Interface)

## ✨ Features

- **🎙️ Automatic Transcription**: converts video speech to text with high accuracy.
- **🌍 Smart Translation**: 
  - Automatically translates English to **Chinese (Simplified)**.
  - Translates other languages to **English (UK)**.
  - customizable Source and Target language selection.
- **⚡ Real-time Processing**: Streamed progress updates keep you informed of every step.
- **📥 Multiple Export Formats**:
  - `*_ori.srt`: Original language subtitles.
  - `*_trans.srt`: Translated subtitles.
  - `*_dual.srt`: **Bilingual subtitles** (Target language on top, Source on bottom).
- **🧹 History Management**: One-click cleanup to remove uploaded videos and cached files.
- **🎨 Premium UI**: A modern, glassmorphism-inspired interface with Drag & Drop support.

## 🚀 Getting Started

### Prerequisites

- **Python 3.8+**
- **FFmpeg**: Must be installed and added to your system PATH.
- **CUDA (Optional)**: Recommended for faster Whisper transcription if you have an NVIDIA GPU.

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/auto_caption_subtitle.git
   cd auto_caption_subtitle
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv .venv
   # Windows
   .\.venv\Scripts\activate
   # Mac/Linux
   source .venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## 🏃 Usage

1. **Start the Web Application**:
   ```bash
   python app.py
   ```

2. **Open your browser** and navigate to:
   ```
   http://127.0.0.1:5000
   ```

3. **Generate Subtitles**:
   - Drag and drop your video file (`.mp4`, `.avi`, `.mov`, `.mkv`).
   - Select your **Source Language** (or leave as Auto).
   - Select your **Target Language** (or leave as Auto).
   - Click **Generate Subtitles**.

4. **Download**:
   - Once complete, download links will appear for Original, Translated, and Dual-Language subtitles.

## 📂 Project Structure

```
auto_caption_subtitle/
├── app.py                 # Flask Backend Application
├── requirements.txt       # Python Dependencies
├── src/
│   ├── pipeline.py        # Core Processing Logic
│   ├── transcriber.py     # Whisper & SRT Handling
│   ├── translator.py      # Translation Logic
│   └── video_processor.py # FFmpeg Video->Audio Conversion
├── templates/
│   └── index.html         # Frontend HTML
├── static/
│   ├── css/style.css      # Styling (Glassmorphism)
│   └── js/script.js       # Frontend Logic (Streaming, Uploads)
└── data/                  # Data Storage (Ignored by Git)
    ├── videos/            # Uploaded Videos
    ├── audios/            # Extracted Audio
    └── transcripts/       # Generated SRT Files
```

## 🛠️ Technology Stack

- **Backend**: Flask, OpenAI Whisper, Deep Translator, FFmpeg-Python
- **Frontend**: HTML5, CSS3, Vanilla JavaScript
- **AI Models**: Whisper (Base model by default)

## 📝 License

[MIT License](LICENSE)