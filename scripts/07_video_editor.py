import os
import sys
import json
import argparse
import subprocess
from datetime import datetime
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from backend.config import get_output_dir, BASE_DIR, VISUAL_MODE

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

def run_cmd(cmd: list) -> None:
    """Runs a subprocess command and handles errors."""
    print(f"  Running: {' '.join(cmd)[:120]}...")
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg command failed with exit code {result.returncode}.\nStderr: {result.stderr}")

def build_raw_video(date_str: str, force: bool = False) -> None:
    output_dir = get_output_dir(date_str)
    scenes_file = output_dir / "scenes.json"
    voice_file = output_dir / "voice.mp3"
    raw_video_file = output_dir / "video_raw.mp4"

    if not scenes_file.exists() or not voice_file.exists():
        raise FileNotFoundError(f"Missing scenes.json or voice.mp3 for {date_str}. Run steps 01-06 first.")

    if raw_video_file.exists() and not force:
        print(f"[07 Video Editor] Raw video already exists at {raw_video_file}. Skipping.")
        return

    # Check for FFmpeg dependency
    ffmpeg_bin = find_ffmpeg()
    if not ffmpeg_bin:
        print("[07 Video Editor] [WARNING] FFmpeg binary was not found on path or backend/bin/.")
        print("[07 Video Editor] Please install FFmpeg (https://ffmpeg.org) and add it to your system PATH.")
        print("[07 Voice Generator / Video Editor] [MOCK] Generating placeholder raw video...")
        
        # Write dummy file in mock mode
        with open(raw_video_file, "wb") as f:
            f.write(b"\x00" * 8000)
        return

    with open(scenes_file, "r", encoding="utf-8") as f:
        scenes = json.load(f)

    if VISUAL_MODE == "gameplay":
        print(f"[07 Video Editor] VISUAL_MODE is set to 'gameplay'. Processing gameplay video background...")
        scene = scenes[0]
        duration = scene["duration"]
        asset_rel = scene["asset_path"]
        asset_path = BASE_DIR / asset_rel
        
        print(f"      Gameplay Clip: {asset_path.name}")
        print(f"      Target Duration: {duration} seconds")
        
        # Loop gameplay video infinitely, overlay audio, trim to duration
        cmd = [
            ffmpeg_bin, "-y",
            "-stream_loop", "-1",
            "-i", str(asset_path),
            "-i", str(voice_file),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
            "-r", "25",
            "-c:a", "aac",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-t", f"{duration:.2f}",
            str(raw_video_file)
        ]
        run_cmd(cmd)
        print(f"[07 Video Editor] Successfully rendered raw video with gameplay background to: {raw_video_file}")
        return

    print(f"[07 Video Editor] Assembling {len(scenes)} scenes into video...")
    
    # Create temporary directory inside outputs/YYYY-MM-DD/temp/ for raw clip processing
    temp_dir = output_dir / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    clip_files = []
    
    try:
        # 1. Process each scene asset into a standard 1080p 25fps video clip of exact duration
        for idx, scene in enumerate(scenes):
            scene_idx = idx + 1
            duration = scene["duration"]
            asset_rel = scene["asset_path"]
            asset_path = BASE_DIR / asset_rel
            
            clip_path = temp_dir / f"scene_{scene_idx:02d}.mp4"
            clip_files.append(clip_path)
            
            # Re-scale to 1080p, force 25fps, and match duration
            if scene["asset_type"] == "image":
                # Convert image to video clip loop
                cmd = [
                    ffmpeg_bin, "-y",
                    "-loop", "1",
                    "-i", str(asset_path),
                    "-c:v", "libx264",
                    "-t", str(duration),
                    "-pix_fmt", "yuv420p",
                    "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
                    "-r", "25",
                    str(clip_path)
                ]
            else:
                # Loop video clip if it's shorter than required, otherwise trim
                cmd = [
                    ffmpeg_bin, "-y",
                    "-stream_loop", "-1",
                    "-i", str(asset_path),
                    "-c:v", "libx264",
                    "-t", str(duration),
                    "-pix_fmt", "yuv420p",
                    "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
                    "-r", "25",
                    "-an",  # strip audio from stock video clip
                    str(clip_path)
                ]
                
            run_cmd(cmd)

        # 2. Write the list of processed clips to a text file for concatenation
        concat_list_file = temp_dir / "concat_list.txt"
        with open(concat_list_file, "w", encoding="utf-8") as f:
            for clip in clip_files:
                # Escape path for FFmpeg demuxer
                escaped_path = str(clip.resolve()).replace("\\", "/")
                f.write(f"file '{escaped_path}'\n")

        # 3. Concatenate all visual clips into a single video track
        merged_visuals = temp_dir / "merged_visuals.mp4"
        print("[07 Video Editor] Concatenating visual clips...")
        cmd = [
            ffmpeg_bin, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_list_file),
            "-c", "copy",
            str(merged_visuals)
        ]
        run_cmd(cmd)

        # 4. Merge voice.mp3 audio track with the visual track
        print("[07 Video Editor] Multiplexing audio and video...")
        cmd = [
            ffmpeg_bin, "-y",
            "-i", str(merged_visuals),
            "-i", str(voice_file),
            "-c:v", "copy",
            "-c:a", "aac",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-shortest",
            str(raw_video_file)
        ]
        run_cmd(cmd)
        
        print(f"[07 Video Editor] Successfully rendered raw video to: {raw_video_file}")
        
    finally:
        # Cleanup temp clips directory
        print("[07 Video Editor] Cleaning up temporary rendering assets...")
        for clip in clip_files:
            if clip.exists():
                try:
                    os.remove(clip)
                except OSError:
                    pass
        if (temp_dir / "concat_list.txt").exists():
            try:
                os.remove(temp_dir / "concat_list.txt")
            except OSError:
                pass
        if (temp_dir / "merged_visuals.mp4").exists():
            try:
                os.remove(temp_dir / "merged_visuals.mp4")
            except OSError:
                pass
        try:
            os.rmdir(temp_dir)
        except OSError:
            pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Assemble video and audio tracks.")
    parser.add_argument(
        "--date",
        type=str,
        default=datetime.now().strftime("%Y-%m-%d"),
        help="Date directory name (YYYY-MM-DD). Defaults to today's date.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force regeneration of the video, overwriting any existing one.",
    )
    args = parser.parse_args()

    try:
        build_raw_video(args.date, args.force)
    except Exception as e:
        print(f"[ERROR] Step 07 Video Editor failed: {e}", file=sys.stderr)
        sys.exit(1)
