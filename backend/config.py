import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env")

# ------------------------------------------------------------------------------
# Directory Setup & Auto-Creation
# ------------------------------------------------------------------------------
ASSETS_DIR = BASE_DIR / "assets"
ASSETS_AUDIO_DIR = ASSETS_DIR / "audio"
ASSETS_IMAGES_DIR = ASSETS_DIR / "images"
ASSETS_THUMBNAILS_DIR = ASSETS_DIR / "thumbnails"
ASSETS_GAMEPLAY_DIR = ASSETS_DIR / "gameplay"
OUTPUTS_DIR = BASE_DIR / "outputs"
DATABASE_DIR = BASE_DIR / "database"
LOGS_DIR = BASE_DIR / "logs"

for directory in [
    ASSETS_DIR,
    ASSETS_AUDIO_DIR,
    ASSETS_IMAGES_DIR,
    ASSETS_THUMBNAILS_DIR,
    ASSETS_GAMEPLAY_DIR,
    OUTPUTS_DIR,
    DATABASE_DIR,
    LOGS_DIR,
]:
    directory.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------------------------
# Configuration Variables
# ------------------------------------------------------------------------------
NICHE = os.getenv("NICHE", "AI-Generated Fictional Reddit Stories and Confessions")

# LLM Providers
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").lower()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Mock Pipeline for offline testing
has_llm_key = (LLM_PROVIDER == "gemini" and bool(GEMINI_API_KEY)) or (LLM_PROVIDER == "openai" and bool(OPENAI_API_KEY))
MOCK_PIPELINE = os.getenv("MOCK_PIPELINE", "false").lower() in ("true", "1")
if not has_llm_key:
    MOCK_PIPELINE = True


# Stock APIs
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY", "")

# Text-To-Speech
TTS_PROVIDER = os.getenv("TTS_PROVIDER", "edge-tts").lower()
EDGE_TTS_VOICE = os.getenv("EDGE_TTS_VOICE", "en-US-GuyNeural")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
PIPER_MODEL_PATH = os.getenv("PIPER_MODEL_PATH", "")
PIPER_EXE_PATH = os.getenv("PIPER_EXE_PATH", "")

# Whisper
WHISPER_PROVIDER = os.getenv("WHISPER_PROVIDER", "openai").lower()

# Visual Mode (choices: gameplay, stock)
VISUAL_MODE = os.getenv("VISUAL_MODE", "gameplay").lower()
GAMEPLAY_VIDEO_FILE = os.getenv("GAMEPLAY_VIDEO_FILE", "")

# Notifications
NOTIFICATION_PROVIDER = os.getenv("NOTIFICATION_PROVIDER", "none").lower()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
NOTIFY_EMAIL = os.getenv("NOTIFY_EMAIL", "")

# Database Path
DB_PATH = DATABASE_DIR / "pipeline.db"

# FFMPEG Path Configuration & Process PATH Injection
FFMPEG_DIR = os.getenv("FFMPEG_DIR", "")
LOCAL_BIN = BASE_DIR / "backend" / "bin"

paths_to_add = []
if FFMPEG_DIR and os.path.exists(FFMPEG_DIR):
    paths_to_add.append(str(Path(FFMPEG_DIR).resolve()))
if LOCAL_BIN.exists():
    paths_to_add.append(str(LOCAL_BIN.resolve()))

if paths_to_add:
    os.environ["PATH"] = os.pathsep.join(paths_to_add) + os.pathsep + os.environ["PATH"]

# ------------------------------------------------------------------------------
# Helper Functions
# ------------------------------------------------------------------------------
def get_output_dir(date_str: str) -> Path:
    """Returns the dated output directory and ensures it exists."""
    path = OUTPUTS_DIR / date_str
    path.mkdir(parents=True, exist_ok=True)
    return path
