# Faceless YouTube Shorts Automation Pipeline

An automated pipeline to generate faceless, high-retention YouTube Shorts (or TikToks/Reels) about interesting niches like "Forgotten Inventions & Failed Tech of the 20th Century." The pipeline researches a topic, drafts a script, fact-checks it, generates a synthetic voiceover, overlays relevant stock media or background gameplay footage, adds styled subtitles, designs a thumbnail, and drafts SEO-optimized metadata.

---

## Features

- **Topic Generator**: Recommends engaging topics in a configured niche.
- **Research Agent & Script Writer**: Conducts internet research and writes a highly engaging short-form script.
- **Fact-Checker**: Automatically scans generated scripts for accuracy and amends errors.
- **Voice Generator**: Generates high-quality voiceover audio (supporting Edge-TTS, ElevenLabs, OpenAI TTS, or local Piper).
- **Scene Planner & Video Editor**: Combines audio, background gameplay or stock footage, overlays transitions, and mixes final video.
- **Subtitle Generator**: Transcribes audio and generates precise, word-by-word styled subtitles overlaid on the video (via OpenAI Whisper or local Whisper).
- **Thumbnail Designer**: Creates dynamic thumbnails using Pillow with bold text rendering.
- **SEO Draft Generator**: Auto-generates optimized titles, descriptions, and hashtags.
- **Local Web UI**: A FastAPI-based dashboard to visualize runs, manage generated videos, and launch pipeline runs.

---

## Tech Stack

- **Core**: Python 3.10+
- **APIs & LLMs**: Google Gemini (Google GenAI SDK), OpenAI API
- **Web App / UI**: FastAPI, SQLite (for database and tracking runs), HTML5, CSS3, Vanilla JS
- **Voice & Subtitles**: edge-tts, ElevenLabs, OpenAI Whisper, or local Whisper
- **Media Processing**: FFmpeg (via subprocesses), Pillow (PIL) for image and thumbnail manipulation

---

## Prerequisites & Installation

### 1. Clone the Repository
```bash
git clone <your-repository-url>
cd Video_generator
```

### 2. Set Up a Virtual Environment & Install Dependencies
```bash
# Create virtual environment
python -m venv .venv

# Activate it
# On Windows:
.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate

# Install required Python packages
pip install -r requirements.txt
```

*Note: If you plan on using **local Whisper** for transcribing subtitles instead of OpenAI's API, you need to manually install PyTorch and OpenAI Whisper:*
```bash
pip install openai-whisper torch
```

### 3. Configure Environment Variables
Copy the template `.env.example` file to create your own local `.env`:
```bash
cp .env.example .env
```
Open `.env` and fill in the required configuration:
- Set `GEMINI_API_KEY` or `OPENAI_API_KEY` (depending on your choice of LLM provider).
- Set `PEXELS_API_KEY` and `PIXABAY_API_KEY` if using stock footage visual mode.
- Set `TTS_PROVIDER` (e.g. `edge-tts`) and configuring options.
- Set `FFMPEG_DIR` if your system does not have FFmpeg installed globally.

### 4. Install FFmpeg
The video editor requires FFmpeg to crop, join, and burn subtitles.
- **Windows**: Download FFmpeg and add the path to the bin folder to your system environment variables, OR set the `FFMPEG_DIR` variable in your `.env` to point to the directory containing `ffmpeg.exe` (e.g. `C:\ffmpeg\bin`).
- **macOS**: `brew install ffmpeg`
- **Linux**: `sudo apt install ffmpeg`

### 5. Setup Background Gameplay Footage
If you are using `VISUAL_MODE="gameplay"` (default), you must populate the `assets/gameplay/` folder with your own gameplay videos (e.g., Minecraft parkour, GTA V, Subway Surfers) in `.mp4` format. 
These files are **not included** in this repository due to their large size and licensing restrictions.

---

## How to Run

### Run the Pipeline Manually
You can run the entire sequential pipeline end-to-end from the command line:

```bash
python run_pipeline.py
```

#### Override Niche or Custom Topic
To force the pipeline to generate a video on a specific topic instead of choosing one automatically:
```bash
python run_pipeline.py --topic "The Flying Platform Hoverboard"
```

### Run the Web Dashboard
You can also launch the FastAPI web server to run the pipeline, monitor status, and preview output videos:
```bash
python backend/server.py
```
Then navigate to `http://localhost:8000` in your web browser.

---

## Roadmap

- [ ] **Automated Cloud Hosting**: Deploy backend to GCP/AWS or render videos on lightweight cloud instances.
- [ ] **Automated Daily Scheduling**: Implement cron-like scheduling to automatically run, generate, and upload/schedule videos on YouTube.
- [ ] **Direct Social Uploads**: Integrate YouTube Data API and TikTok API for automated uploads directly from the dashboard.
- [ ] **Enhanced Theme Customization**: Pre-build specific animation presets, transition styles, and text font styling in the UI.
