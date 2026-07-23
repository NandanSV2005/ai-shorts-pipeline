import os
import sys
import argparse
import subprocess
from datetime import datetime
from pathlib import Path
import json

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from backend.config import get_output_dir, WHISPER_PROVIDER, OPENAI_API_KEY, MOCK_PIPELINE, BASE_DIR

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

def find_ffmpeg() -> str:
    """Checks if ffmpeg is available on system PATH or local bin/ directory."""
    local_ffmpeg = BASE_DIR / "backend" / "bin" / "ffmpeg.exe"
    if local_ffmpeg.exists():
        return str(local_ffmpeg)
    
    # Try calling ffmpeg
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return "ffmpeg"
    except FileNotFoundError:
        pass
        
    return ""

def format_srt_time(seconds: float) -> str:
    """Formats float seconds into SRT timestamp format: HH:MM:SS,mmm"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

def generate_estimated_srt(script_file: Path, srt_file: Path) -> None:
    """Generates a mock/estimated SRT file based on sentence pacing in script.txt."""
    print("[08 Subtitles] Generating estimated SRT file from script text pacing...")
    text = extract_narration(script_file)
    
    # Split text into sentences or clauses for subtitle segments
    sentences = [s.strip() for s in re_split_sentences(text) if s.strip()]
    
    with open(srt_file, "w", encoding="utf-8") as f:
        current_time = 0.0
        for idx, sentence in enumerate(sentences):
            word_count = len(sentence.split())
            if word_count == 0:
                continue
            
            # Estimate duration: ~2.5 words per second
            duration = max(1.5, word_count / 2.5)
            
            start_str = format_srt_time(current_time)
            end_str = format_srt_time(current_time + duration)
            
            f.write(f"{idx + 1}\n")
            f.write(f"{start_str} --> {end_str}\n")
            f.write(f"{sentence}\n\n")
            
            current_time += duration

def re_split_sentences(text: str) -> list:
    """Splits text on punctuation (., !, ?) but keeps abbreviations intact."""
    import re
    # Simple regex split by sentence boundaries
    sentence_end = re.compile(r'(?<=[.!?])\s+')
    return sentence_end.split(text)

def run_openai_whisper(voice_file: Path, srt_file: Path) -> None:
    """Calls OpenAI audio transcriptions API to get SRT content."""
    print("[08 Subtitles] Transcribing audio with OpenAI Whisper API...")
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is not configured in .env")
        
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
    
    with open(voice_file, "rb") as audio:
        srt_content = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio,
            response_format="srt"
        )
        
    # The API returns the raw SRT string
    assert isinstance(srt_content, str)
    with open(srt_file, "w", encoding="utf-8") as f:
        f.write(srt_content)

def run_local_whisper(voice_file: Path, srt_file: Path) -> None:
    """Uses local Whisper library if installed."""
    print("[08 Subtitles] Transcribing audio with local Whisper model...")
    try:
        import whisper  # type: ignore
    except ImportError:
        raise ImportError("Local Whisper package not installed. Run: pip install openai-whisper torch")
        
    model = whisper.load_model("base")
    result = model.transcribe(str(voice_file))
    
    segments = result.get("segments", [])
    if not isinstance(segments, list):
        segments = []
    with open(srt_file, "w", encoding="utf-8") as f:
        for idx, seg_item in enumerate(segments):
            if not isinstance(seg_item, dict):
                continue
            start = float(seg_item.get("start", 0.0))
            end = float(seg_item.get("end", 0.0))
            text = str(seg_item.get("text", "")).strip()
            
            start_str = format_srt_time(start)
            end_str = format_srt_time(end)
            
            f.write(f"{idx + 1}\n")
            f.write(f"{start_str} --> {end_str}\n")
            f.write(f"{text}\n\n")

def parse_srt_time(time_str: str) -> float:
    """Parses SRT timestamp 'HH:MM:SS,mmm' to float seconds."""
    time_str = time_str.strip().replace(",", ".")
    parts = time_str.split(":")
    if len(parts) != 3:
        return 0.0
    h = int(parts[0])
    m = int(parts[1])
    s = float(parts[2])
    return h * 3600 + m * 60 + s

def split_words_into_chunks(words: list, min_words: int = 5, max_words: int = 8) -> list:
    chunks = []
    total_words = len(words)
    i = 0
    while i < total_words:
        remaining = total_words - i
        if remaining <= max_words:
            chunks.append(words[i:])
            break
        elif remaining < min_words + min_words:
            half = remaining // 2
            chunks.append(words[i:i+half])
            chunks.append(words[i+half:])
            break
        else:
            take = 6
            chunks.append(words[i:i+take])
            i += take
    return chunks

def rechunk_srt(srt_path: Path, min_words: int = 5, max_words: int = 8) -> None:
    if not srt_path.exists():
        return
        
    import re
    with open(srt_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    blocks = re.split(r'\n\s*\n', content.strip())
    all_words = []
    for block in blocks:
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if len(lines) < 3:
            continue
        time_line = lines[1]
        text = " ".join(lines[2:])
        
        times = time_line.split("-->")
        if len(times) != 2:
            continue
        start_seconds = parse_srt_time(times[0])
        end_seconds = parse_srt_time(times[1])
        
        words = text.split()
        if not words:
            continue
            
        total_words = len(words)
        total_duration = end_seconds - start_seconds
        for idx, word in enumerate(words):
            word_start = start_seconds + total_duration * (idx / total_words)
            word_end = start_seconds + total_duration * ((idx + 1) / total_words)
            all_words.append({
                "word": word,
                "start": word_start,
                "end": word_end
            })
            
    if not all_words:
        return
        
    new_segments = []
    i = 0
    total_words_count = len(all_words)
    
    while i < total_words_count:
        remaining = total_words_count - i
        if remaining <= max_words:
            take = remaining
        elif remaining < min_words + min_words:
            take = remaining // 2
        else:
            take = 6
            
        chunk_words = all_words[i:i+take]
        chunk_text = " ".join([w["word"] for w in chunk_words])
        chunk_start = chunk_words[0]["start"]
        chunk_end = chunk_words[-1]["end"]
        
        new_segments.append({
            "start": chunk_start,
            "end": chunk_end,
            "text": chunk_text
        })
        i += take
        
    with open(srt_path, "w", encoding="utf-8") as f:
        for idx, seg in enumerate(new_segments):
            start_str = format_srt_time(seg["start"])
            end_str = format_srt_time(seg["end"])
            f.write(f"{idx + 1}\n")
            f.write(f"{start_str} --> {end_str}\n")
            f.write(f"{seg['text']}\n\n")

def get_total_srt_duration(srt_path: Path) -> float:
    if not srt_path.exists():
        return 0.0
    import re
    with open(srt_path, "r", encoding="utf-8") as f:
        content = f.read()
    matches = re.findall(r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})', content)
    if not matches:
        return 0.0
    last_end_str = matches[-1][1].replace(",", ".")
    try:
        parts = last_end_str.split(":")
        if len(parts) == 3:
            h = int(parts[0])
            m = int(parts[1])
            s = float(parts[2])
            return h * 3600 + m * 60 + s
    except Exception:
        pass
    return 0.0

def find_split_timestamp(script_path: Path, srt_path: Path) -> float:
    words_before = 0
    found_split = False
    if not script_path.exists():
        return -1.0
        
    with open(script_path, "r", encoding="utf-8") as f:
        for line in f:
            line_str = line.strip()
            if not line_str:
                continue
            if line_str == "[SPLIT POINT]":
                found_split = True
                break
            if line_str.startswith("[") and line_str.endswith("]"):
                continue
            words_before += len(line_str.split())
            
    if not found_split:
        return -1.0

    if not srt_path.exists():
        return -1.0
        
    import re
    with open(srt_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    blocks = re.split(r'\n\s*\n', content.strip())
    cumulative_words = 0
    split_time = 0.0
    
    for block in blocks:
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if len(lines) < 3:
            continue
        time_line = lines[1]
        text_lines = lines[2:]
        text = " ".join(text_lines)
        
        end_seconds = 0.0
        times = time_line.split("-->")
        if len(times) == 2:
            end_time_str = times[1].strip().replace(",", ".")
            try:
                parts = end_time_str.split(":")
                if len(parts) == 3:
                    h = int(parts[0])
                    m = int(parts[1])
                    s = float(parts[2])
                    end_seconds = h * 3600 + m * 60 + s
                else:
                    end_seconds = 0.0
            except Exception:
                end_seconds = 0.0
                
        block_words = len(text.split())
        cumulative_words += block_words
        
        if cumulative_words >= words_before:
            split_time = end_seconds
            break
            
    return split_time if split_time > 0.0 else -1.0

def split_video_into_parts(output_dir: Path, final_video: Path, script_file: Path, srt_file: Path, ffmpeg_bin: str) -> None:
    part1_file = output_dir / "video_part1.mp4"
    part2_file = output_dir / "video_part2.mp4"
    
    if not final_video.exists():
        raise FileNotFoundError(f"Final video not found: {final_video}")

    if not ffmpeg_bin:
        print("[08 Subtitles] [MOCK] Generating placeholders for Part 1 & Part 2...")
        with open(part1_file, "wb") as f:
            f.write(b"\x00" * 4000)
        with open(part2_file, "wb") as f:
            f.write(b"\x00" * 4000)
        return

    total_dur = get_total_srt_duration(srt_file)
    if total_dur <= 0.0:
        total_dur = 240.0
        
    split_time = find_split_timestamp(script_file, srt_file)
    if split_time <= 0.0 or split_time >= total_dur:
        split_time = total_dur / 2.0
        print(f"[08 Subtitles] [WARNING] Natural split point not found. Splitting video in half at {split_time:.2f} seconds.")
    else:
        print(f"[08 Subtitles] Splitting video at natural [SPLIT POINT] marker: {split_time:.2f} seconds.")
        
    cmd_part1 = [
        ffmpeg_bin, "-y",
        "-i", str(final_video),
        "-t", f"{split_time:.3f}",
        "-c", "copy",
        str(part1_file)
    ]
    cmd_part2 = [
        ffmpeg_bin, "-y",
        "-ss", f"{split_time:.3f}",
        "-i", str(final_video),
        "-c", "copy",
        "-avoid_negative_ts", "make_zero",
        str(part2_file)
    ]
    
    print(f"[08 Subtitles] Rendering Part 1 (0.00s to {split_time:.2f}s)...")
    subprocess.run(cmd_part1, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"[08 Subtitles] Rendering Part 2 ({split_time:.2f}s to {total_dur:.2f}s)...")
    subprocess.run(cmd_part2, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("[08 Subtitles] Split process completed successfully.")

def burn_subtitles(ffmpeg_bin: str, raw_video: Path, srt_file: Path, output_video: Path) -> None:
    """Uses FFmpeg to burn subtitles from srt_file into the raw video."""
    print("[08 Subtitles] Burning subtitles into video...")
    
    # FFmpeg subtitles filter needs escaped/slashed paths on Windows
    # Specifically, colons and backslashes must be escaped for the filter parameter
    srt_filter_path = str(srt_file.resolve()).replace("\\", "/")
    # Escape colon for Windows, e.g. "C:/path" -> "C\\:/path"
    srt_filter_path = srt_filter_path.replace(":", "\\:")
    
    cmd = [
        ffmpeg_bin, "-y",
        "-i", str(raw_video),
        "-vf", f"subtitles='{srt_filter_path}':force_style='FontName=Arial,FontSize=20,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=2,MarginV=180'",
        "-c:a", "copy",
        str(output_video)
    ]
    
    # Run the burn-in
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg burning subtitles failed: {result.stderr}")

def generate_subtitles_and_render(date_str: str, force: bool = False, parts: int | None = None) -> None:
    output_dir = get_output_dir(date_str)
    script_file = output_dir / "script.txt"
    voice_file = output_dir / "voice.mp3"
    raw_video = output_dir / "video_raw.mp4"
    srt_file = output_dir / "subtitles.srt"
    final_video = output_dir / "video.mp4"
    part1_file = output_dir / "video_part1.mp4"
    part2_file = output_dir / "video_part2.mp4"

    if not script_file.exists() or not voice_file.exists() or not raw_video.exists():
        raise FileNotFoundError(f"Missing required input files for step 08 on date {date_str}.")

    # Resolve parts configuration
    metadata_file = output_dir / "metadata.json"
    if parts is None and metadata_file.exists():
        try:
            with open(metadata_file, "r", encoding="utf-8") as f:
                parts = json.load(f).get("parts", 1)
        except Exception:
            parts = 1
    parts_count = parts if parts is not None else 1

    if final_video.exists() and srt_file.exists() and not force:
        inputs_updated = (raw_video.stat().st_mtime > final_video.stat().st_mtime or 
                          voice_file.stat().st_mtime > final_video.stat().st_mtime or 
                          script_file.stat().st_mtime > final_video.stat().st_mtime)
        missing_parts = (parts_count == 2 and (not part1_file.exists() or not part2_file.exists()))
        
        if inputs_updated:
            print(f"[08 Subtitles] Inputs updated after video.mp4 was created. Forcing subtitle re-burn.")
        elif missing_parts:
            print(f"[08 Subtitles] Split parts requested (parts=2) but video_part1.mp4 or video_part2.mp4 missing. Rendering split parts.")
            ffmpeg_bin = find_ffmpeg()
            split_video_into_parts(output_dir, final_video, script_file, srt_file, ffmpeg_bin)
            return
        else:
            print(f"[08 Subtitles] Subtitled video already exists at {final_video} and is up to date. Skipping.")
            return

    # 1. Transcribe audio to generate subtitles.srt
    subtitles_raw_file = output_dir / "subtitles_raw.srt"
    if subtitles_raw_file.exists() and (voice_file.stat().st_mtime <= subtitles_raw_file.stat().st_mtime and script_file.stat().st_mtime <= subtitles_raw_file.stat().st_mtime):
        print(f"[08 Subtitles] Using raw subtitles generated during voice synthesis...")
        import shutil
        shutil.copy(subtitles_raw_file, srt_file)
    elif MOCK_PIPELINE:
        generate_estimated_srt(script_file, srt_file)
        print(f"[08 Subtitles] Generated estimated subtitles file: {srt_file}")
    else:
        try:
            if WHISPER_PROVIDER == "openai":
                run_openai_whisper(voice_file, srt_file)
            elif WHISPER_PROVIDER == "local":
                run_local_whisper(voice_file, srt_file)
            else:
                raise ValueError(f"Unknown WHISPER_PROVIDER: {WHISPER_PROVIDER}")
            print(f"[08 Subtitles] Successfully saved transcribed subtitles: {srt_file}")
        except Exception as e:
            print(f"[08 Subtitles] Transcription failed ({e}). Falling back to estimated alignment.")
            generate_estimated_srt(script_file, srt_file)

    # Re-chunk SRT to Shorts-style 5-8 word segments
    try:
        rechunk_srt(srt_file)
        print("[08 Subtitles] Re-chunked SRT to Shorts-style 5-8 word segments.")
    except Exception as e:
        print(f"[08 Subtitles] [WARNING] Failed to re-chunk SRT: {e}")

    # 2. Burn subtitles into raw video using FFmpeg
    ffmpeg_bin = find_ffmpeg()
    if not ffmpeg_bin:
        print("[08 Subtitles] [WARNING] FFmpeg not found. Subtitles cannot be burned in.")
        print("[08 Subtitles] [MOCK] Copying raw video placeholder directly to final video...")
        
        # In mock fallback mode, copy raw video file to final video file
        import shutil
        shutil.copy(raw_video, final_video)
    else:
        try:
            burn_subtitles(ffmpeg_bin, raw_video, srt_file, final_video)
            print(f"[08 Subtitles] Successfully rendered subtitled video to: {final_video}")
        except Exception as e:
            print(f"[ERROR] Burning subtitles failed: {e}. Copying raw video to final video as fallback.")
            import shutil
            shutil.copy(raw_video, final_video)

    # 3. Split final video into two parts for YouTube Shorts if requested
    if parts_count == 2:
        try:
            split_video_into_parts(output_dir, final_video, script_file, srt_file, ffmpeg_bin)
        except Exception as e:
            print(f"[08 Subtitles] [ERROR] Failed to split video: {e}")
    else:
        print("[08 Subtitles] 'parts' configuration is set to 1. Skipping video split.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Transcribe audio and burn subtitles into video.")
    parser.add_argument(
        "--date",
        type=str,
        default=datetime.now().strftime("%Y-%m-%d"),
        help="Date directory name (YYYY-MM-DD). Defaults to today's date.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force transcription and subtitle rendering, overwriting any existing files.",
    )
    parser.add_argument(
        "--parts",
        type=int,
        default=None,
        help="Number of video parts (1 or 2).",
    )
    args = parser.parse_args()

    try:
        generate_subtitles_and_render(args.date, args.force, args.parts)
    except Exception as e:
        print(f"[ERROR] Step 08 Subtitle Generator failed: {e}", file=sys.stderr)
        sys.exit(1)
