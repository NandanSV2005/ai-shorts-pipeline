import os
import sys
import argparse
import asyncio
import subprocess
import requests  # type: ignore
from datetime import datetime
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from backend.config import (
    get_output_dir,
    TTS_PROVIDER,
    EDGE_TTS_VOICE,
    TTS_RATE,
    TTS_SPEED,
    OPENAI_API_KEY,
    ELEVENLABS_API_KEY,
    ELEVENLABS_VOICE_ID,
    PIPER_MODEL_PATH,
    PIPER_EXE_PATH,
    MOCK_PIPELINE
)

def extract_narration(script_path: Path) -> str:
    """Reads script.txt and extracts only the lines spoken by the narrator."""
    if not script_path.exists():
        raise FileNotFoundError(f"Script file not found at {script_path}")
        
    narration_lines = []
    with open(script_path, "r", encoding="utf-8") as f:
        for line in f:
            line_str = line.strip()
            if not line_str:
                continue
            # Skip visual scene directions and section headers in brackets
            if line_str.startswith("[") and line_str.endswith("]"):
                continue
            narration_lines.append(line_str)
            
    return " ".join(narration_lines)

def run_mock_tts(text: str, output_file: Path) -> None:
    """Generates a low-volume pulsed beep MP3 file with duration proportional to the text word count."""
    word_count = len(text.split())
    # Average speech rate at 1.5x speed is ~3.75 words per second (225 words per minute)
    duration = max(3, int(word_count / 3.75))
    print(f"[05 Voice Generator] [MOCK] Generating a {duration}-second mock beep MP3 placeholder (Rate: {TTS_RATE}, Speed: {TTS_SPEED}x)...")
    
    # Run FFmpeg command to generate pulsed beep audio
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"sine=f=400:r=24000,volume=0.05*lt(mod(t\\,1.5)\\,0.2)",
        "-t", str(duration),
        "-q:a", "9",
        "-acodec", "libmp3lame",
        str(output_file)
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        print("[05 Voice Generator] [MOCK] FFmpeg binary not found on path. Creating empty file instead.")
        with open(output_file, "wb") as f:
            f.write(b"\x00" * 4000)

async def run_edge_tts(text: str, output_file: Path, srt_file: Path) -> None:
    """Calls Edge TTS API to generate voiceover and timing subtitles."""
    print(f"[05 Voice Generator] Using Edge-TTS (Voice: {EDGE_TTS_VOICE}, Rate: {TTS_RATE})...")
    import edge_tts
    communicate = edge_tts.Communicate(text, EDGE_TTS_VOICE, rate=TTS_RATE, boundary="WordBoundary")
    submaker = edge_tts.SubMaker()
    with open(output_file, "wb") as fp:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                fp.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                submaker.feed(chunk)
                
    # Save raw srt timings
    with open(srt_file, "w", encoding="utf-8") as f:
        f.write(submaker.get_srt())
    print(f"[05 Voice Generator] Saved raw subtitles to: {srt_file}")

def run_openai_tts(text: str, output_file: Path) -> None:
    """Calls OpenAI API to generate voiceover."""
    print(f"[05 Voice Generator] Using OpenAI TTS (Speed: {TTS_SPEED}x)...")
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is not configured in .env")
        
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.audio.speech.create(
        model="tts-1",
        voice="alloy",
        input=text,
        speed=TTS_SPEED
    )
    response.write_to_file(str(output_file))

def run_elevenlabs_tts(text: str, output_file: Path) -> None:
    """Calls ElevenLabs API to generate voiceover."""
    print(f"[05 Voice Generator] Using ElevenLabs (Voice ID: {ELEVENLABS_VOICE_ID})...")
    if not ELEVENLABS_API_KEY:
        raise ValueError("ELEVENLABS_API_KEY is not configured in .env")
        
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": ELEVENLABS_API_KEY
    }
    data = {
        "text": text,
        "model_id": "eleven_monolingual_v1",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75
        }
    }
    response = requests.post(url, json=data, headers=headers)
    response.raise_for_status()
    with open(output_file, "wb") as f:
        f.write(response.content)

def run_piper_tts(text: str, output_file: Path) -> None:
    """Wraps Piper CLI to generate voiceover."""
    print(f"[05 Voice Generator] Using Piper local TTS...")
    if not PIPER_MODEL_PATH or not os.path.exists(PIPER_MODEL_PATH):
        raise ValueError(f"Piper model path does not exist: {PIPER_MODEL_PATH}")
        
    piper_bin = PIPER_EXE_PATH if PIPER_EXE_PATH else "piper"
    
    # We output to a temporary WAV file, then encode as MP3 via FFmpeg
    temp_wav = output_file.with_suffix(".wav")
    
    # Run Piper command: echo "Text" | piper --model voice.onnx --output_file output.wav
    # piper takes text on stdin
    proc = subprocess.Popen(
        [piper_bin, "--model", PIPER_MODEL_PATH, "--output_file", str(temp_wav)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    stdout, stderr = proc.communicate(input=text)
    
    if proc.returncode != 0:
        raise RuntimeError(f"Piper process failed: {stderr}")
        
    # Convert WAV to MP3 using FFmpeg
    cmd = [
        "ffmpeg", "-y",
        "-i", str(temp_wav),
        "-acodec", "libmp3lame",
        "-q:a", "2",
        str(output_file)
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # Delete temporary WAV file
    if temp_wav.exists():
        os.remove(temp_wav)

def generate_voiceover(date_str: str, force: bool = False) -> None:
    output_dir = get_output_dir(date_str)
    script_file = output_dir / "script.txt"
    voice_file = output_dir / "voice.mp3"
    srt_raw_file = output_dir / "subtitles_raw.srt"

    if not script_file.exists():
        raise FileNotFoundError(f"Script file not found for {date_str}. Run 03_script_writer.py first.")

    if voice_file.exists() and not force:
        if script_file.stat().st_mtime > voice_file.stat().st_mtime:
            print(f"[05 Voice Generator] script.txt was updated after voice.mp3 was created. Forcing voiceover regeneration.")
        else:
            print(f"[05 Voice Generator] Voice file already exists at {voice_file} and is up to date. Skipping.")
            return

    text = extract_narration(script_file)
    if not text:
        raise ValueError("No spoken narration found in script.txt.")

    print(f"[05 Voice Generator] Extracted {len(text.split())} words of spoken narration.")

    if MOCK_PIPELINE:
        run_mock_tts(text, voice_file)
        print(f"[05 Voice Generator] Mock voice file saved successfully.")
        return

    try:
        if TTS_PROVIDER == "edge-tts":
            asyncio.run(run_edge_tts(text, voice_file, srt_raw_file))
        elif TTS_PROVIDER == "openai":
            run_openai_tts(text, voice_file)
        elif TTS_PROVIDER == "elevenlabs":
            run_elevenlabs_tts(text, voice_file)
        elif TTS_PROVIDER == "piper":
            run_piper_tts(text, voice_file)
        else:
            raise ValueError(f"Unknown TTS_PROVIDER: {TTS_PROVIDER}")
        
        print(f"[05 Voice Generator] Voiceover successfully generated and saved: {voice_file}")
        
    except Exception as e:
        print(f"[05 Voice Generator] Primary TTS provider '{TTS_PROVIDER}' failed: {e}. Falling back to edge-tts.")
        try:
            # Fallback to edge-tts if not mock
            asyncio.run(run_edge_tts(text, voice_file, srt_raw_file))
            print(f"[05 Voice Generator] Fallback voiceover saved to: {voice_file}")
        except Exception as fallback_err:
            print(f"[ERROR] Fallback edge-tts failed too: {fallback_err}. Generating mock silent audio.")
            run_mock_tts(text, voice_file)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate voiceover for the daily script.")
    parser.add_argument(
        "--date",
        type=str,
        default=datetime.now().strftime("%Y-%m-%d"),
        help="Date directory name (YYYY-MM-DD). Defaults to today's date.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force regeneration of the voiceover, overwriting any existing one.",
    )
    args = parser.parse_args()

    try:
        generate_voiceover(args.date, args.force)
    except Exception as e:
        print(f"[ERROR] Step 05 Voice Generator failed: {e}", file=sys.stderr)
        sys.exit(1)
