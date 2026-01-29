# AutoCaption Pro 🎥📝

**AutoCaption Pro** is an intelligent, web-based tool designed to automatically generate, translate, and synchronize subtitles for your videos. Powered by OpenAI's **Whisper** model for state-of-the-art speech recognition and **Deep Translator** for multilingual support.


## ✨ Features

- **🚀 Batch Video Upload**: Upload multiple videos at once and process them in a queue.
- **🎙️ Automatic Transcription**: Converts video speech to text with high accuracy using Whisper.
- **🌍 Smart Translation**: 
  - Automatically translates English to **Chinese (Simplified)**.
  - Translates other languages to **English (UK)**.
  - Per-video language selection for customized results.
- **⚡ Sequential Batch Processing**: Processes videos one by one with individual progress tracking.
- **📥 Multiple Export Formats**:
  - `*_ori.srt`: Original language subtitles.
  - `*_trans.srt`: Translated subtitles.
  - `*_dual.srt`: **Bilingual subtitles** (Target on top, Source on bottom).
- **🧹 History Management**: Cleanly wipes uploaded files and generated transcripts.
- **🎨 Premium Wide UI**: A modern, 1000px wide horizontal interface for efficient batch work.
- **🛠️ Auto-Dependency Check**: Automatically installs missing Python packages on startup.

## 🚀 Getting Started

### Prerequisites

- **Python 3.8+**
- **FFmpeg**: Must be installed and added to your system PATH.
- **CUDA (Optional)**: Recommended for faster Whisper transcription (NVIDIA GPU).

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

## 🏃 Usage

1. **Upload**: Drag and drop multiple video files onto the upload area.
2. **Configure**: Set individual **Source** and **Target** languages for each video in the horizontal list.
3. **Process**: Click **Generate All Subtitles**.
4. **Download**: Once a video is marked "Done", use the **Get Files** dropdown to download your chosen SRT format.

## 📂 Project Structure

```
auto_caption_subtitle/
├── app.py                 # Flask Backend & Startup Flow
├── requirements.txt       # Python Dependencies
├── src/
│   ├── dependency_manager.py # Environment & Package Checker
│   ├── pipeline.py        # Batch logic & Subtitle Assembly
│   ├── transcriber.py     # Whisper & SRT Handling
│   ├── translator.py      # Multi-language Translation
│   └── video_processor.py # FFmpeg Conversion
├── templates/
│   └── index.html         # Redesigned Horizontal UI
├── static/
│   ├── css/style.css      # Premium Glassmorphic Styling
│   └── js/script.js       # Batch Logic & Progress Management
└── data/                  # Storage (Auto-created, Git-ignored)
```

## 📝 License

[MIT License](LICENSE)
