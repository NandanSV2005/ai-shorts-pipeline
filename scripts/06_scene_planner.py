import os
import sys
import json
import argparse
import re
import requests  # type: ignore
import urllib.parse
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from backend.config import (
    get_output_dir,
    PEXELS_API_KEY,
    PIXABAY_API_KEY,
    MOCK_PIPELINE,
    VISUAL_MODE,
    GAMEPLAY_VIDEO_FILE,
    BASE_DIR
)
import subprocess


def parse_scenes_and_durations(script_path: Path) -> list:
    """
    Parses script.txt and groups visual scene tags [SCENE: ...]
    with their subsequent narration text to estimate timing.
    """
    with open(script_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Split by lines
    lines = content.split("\n")
    scenes = []
    
    current_scene_desc = "Intro Visual"
    current_narration = []
    
    scene_pattern = re.compile(r"^\[SCENE:\s*(.*)\]$", re.IGNORECASE)
    
    for line in lines:
        line_str = line.strip()
        if not line_str:
            continue
            
        # Check if line is a scene directive
        match = scene_pattern.match(line_str)
        if match:
            # If we already have narration gathered, save previous scene
            if current_narration or len(scenes) > 0:
                text_block = " ".join(current_narration)
                word_count = len(text_block.split())
                # Duration: ~2.5 words per second, min 3 seconds
                duration = max(4.0, round(word_count / 2.5, 1))
                scenes.append({
                    "description": current_scene_desc,
                    "narration": text_block,
                    "duration": duration
                })
            current_scene_desc = match.group(1)
            current_narration = []
        else:
            # Skip structural tags like [HOOK], [BODY], [CTA/OUTRO]
            if line_str.startswith("[") and line_str.endswith("]"):
                continue
            current_narration.append(line_str)
            
    # Add final scene
    if current_narration or current_scene_desc:
        text_block = " ".join(current_narration)
        word_count = len(text_block.split())
        duration = max(4.0, round(word_count / 2.5, 1))
        scenes.append({
            "description": current_scene_desc,
            "narration": text_block,
            "duration": duration
        })
        
    # Filter out empty scenes
    return [s for s in scenes if s["description"]]

def create_fallback_image(description: str, index: int, duration: float, output_path: Path) -> str:
    """Generates a stylish 1080p placeholder image using Pillow."""
    width, height = 1920, 1080
    
    # Create dark gradient background representation (sleek dark mode slate blue)
    img = Image.new("RGB", (width, height), color=(30, 34, 42))
    draw = ImageDraw.Draw(img)
    
    # Draw subtle background border
    draw.rectangle([20, 20, width - 20, height - 20], outline=(70, 75, 90), width=3)
    
    # Write text (using default font as fallback, but sizing up if possible)
    # We use simple built-in font since custom TTFs might not exist in sandbox
    text_scene = f"SCENE {index:02d} ({duration}s)"
    text_desc = description
    
    # Simple line wraps for description
    words = text_desc.split()
    wrapped_lines = []
    current_line = []
    for word in words:
        if len(" ".join(current_line + [word])) > 40:
            wrapped_lines.append(" ".join(current_line))
            current_line = [word]
        else:
            current_line.append(word)
    if current_line:
        wrapped_lines.append(" ".join(current_line))
        
    # Drawing details
    # We will use draw.text with default font. To make it readable, we can output
    # clean lines centered.
    draw.text((100, 200), text_scene, fill=(255, 100, 100))
    
    y = 350
    for line in wrapped_lines:
        draw.text((100, y), line, fill=(255, 255, 255))
        y += 80
        
    draw.text((100, 850), "[Stock Asset Fallback / AI Mock Mode]", fill=(120, 125, 140))
    
    img.save(output_path, "PNG")
    return "image"

def download_pexels_video(query: str, output_path: Path) -> bool:
    """Attempts to search and download a video from Pexels."""
    if not PEXELS_API_KEY:
        return False
        
    url = f"https://api.pexels.com/videos/search?query={urllib.parse.quote(query)}&per_page=3&orientation=landscape"
    headers = {"Authorization": PEXELS_API_KEY}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return False
            
        data = response.json()
        videos = data.get("videos", [])
        if not videos:
            return False
            
        # Select first video and find a good file
        video = videos[0]
        video_files = video.get("video_files", [])
        
        # Look for HD files (1920x1080 or similar)
        selected_link = None
        for vf in video_files:
            width = vf.get("width")
            height = vf.get("height")
            # Prefer 1920x1080
            if width == 1920 and height == 1080:
                selected_link = vf.get("link")
                break
                
        if not selected_link and video_files:
            # Fallback to first available link
            selected_link = video_files[0].get("link")
            
        if selected_link:
            print(f"      Downloading Pexels video: {selected_link[:60]}...")
            vid_response = requests.get(selected_link, stream=True, timeout=30)
            vid_response.raise_for_status()
            with open(output_path, "wb") as f:
                for chunk in vid_response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True
            
    except Exception as e:
        print(f"      Pexels download failed: {e}")
        
    return False

def download_pixabay_image(query: str, output_path: Path) -> bool:
    """Attempts to search and download an image from Pixabay."""
    if not PIXABAY_API_KEY:
        return False
        
    url = f"https://pixabay.com/api/?key={PIXABAY_API_KEY}&q={urllib.parse.quote(query)}&image_type=photo&orientation=horizontal&per_page=3"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return False
            
        data = response.json()
        hits = data.get("hits", [])
        if not hits:
            return False
            
        image_url = hits[0].get("largeImageURL")
        if image_url:
            print(f"      Downloading Pixabay image: {image_url[:60]}...")
            img_response = requests.get(image_url, stream=True, timeout=20)
            img_response.raise_for_status()
            with open(output_path, "wb") as f:
                for chunk in img_response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True
            
    except Exception as e:
        print(f"      Pixabay download failed: {e}")
        
    return False

def find_ffprobe() -> str:
    local_ffprobe = BASE_DIR / "backend" / "bin" / "ffprobe.exe"
    if local_ffprobe.exists():
        return str(local_ffprobe)
    return "ffprobe"

def find_ffmpeg() -> str:
    local_ffmpeg = BASE_DIR / "backend" / "bin" / "ffmpeg.exe"
    if local_ffmpeg.exists():
        return str(local_ffmpeg)
    return "ffmpeg"

def get_media_duration(file_path: Path) -> float:
    ffprobe_bin = find_ffprobe()
    cmd = [
        ffprobe_bin, "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(file_path)
    ]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return float(result.stdout.strip())
    except Exception as e:
        print(f"      [WARNING] Could not get audio duration with ffprobe ({e}). Estimating from file size...")
        if file_path.exists():
            size = file_path.stat().st_size
            return max(5.0, round(size / 16000.0, 1))
        return 60.0

def plan_scenes(date_str: str, force: bool = False) -> list:
    output_dir = get_output_dir(date_str)
    script_file = output_dir / "script.txt"
    scenes_file = output_dir / "scenes.json"
    voice_file = output_dir / "voice.mp3"

    if not script_file.exists():
        raise FileNotFoundError(f"Script file not found for {date_str}. Run 03_script_writer.py first.")

    if VISUAL_MODE == "gameplay" and not voice_file.exists():
        raise FileNotFoundError(f"voice.mp3 not found for {date_str}. Run 05_voice_generator.py first.")

    if scenes_file.exists() and not force:
        print(f"[06 Scene Planner] Scenes already planned for {date_str}. Skipping.")
        with open(scenes_file, "r", encoding="utf-8") as f:
            return json.load(f)

    if VISUAL_MODE == "gameplay":
        print(f"[06 Scene Planner] VISUAL_MODE is set to 'gameplay'. Planning background gameplay video...")
        from backend.config import ASSETS_GAMEPLAY_DIR
        import random
        
        gameplay_video = None
        gameplay_files = [f for f in ASSETS_GAMEPLAY_DIR.glob("*.mp4")]
        
        if GAMEPLAY_VIDEO_FILE:
            spec_file = ASSETS_GAMEPLAY_DIR / GAMEPLAY_VIDEO_FILE
            if spec_file.exists():
                gameplay_video = spec_file
            else:
                print(f"      [WARNING] Configured GAMEPLAY_VIDEO_FILE '{GAMEPLAY_VIDEO_FILE}' not found at {spec_file}.")
        
        if not gameplay_video:
            if gameplay_files:
                gameplay_video = random.choice(gameplay_files)
                print(f"      Selected gameplay video: {gameplay_video.name}")
            else:
                placeholder_file = ASSETS_GAMEPLAY_DIR / "placeholder_gameplay.mp4"
                if not placeholder_file.exists():
                    print(f"      [WARNING] No gameplay videos found in {ASSETS_GAMEPLAY_DIR}.")
                    print(f"      Generating a 30-second color placeholder gameplay video using FFmpeg...")
                    ffmpeg_bin = find_ffmpeg()
                    cmd = [
                        ffmpeg_bin, "-y",
                        "-f", "lavfi", "-i", "color=c=27303c:s=1920x1080:r=25",
                        "-t", "30",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        str(placeholder_file)
                    ]
                    try:
                        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                        print(f"      Generated placeholder gameplay video: {placeholder_file.name}")
                    except Exception as e:
                        print(f"      [ERROR] Failed to generate placeholder video: {e}")
                        with open(placeholder_file, "wb") as f:
                            f.write(b"\x00" * 10000)
                gameplay_video = placeholder_file
        
        voice_duration = get_media_duration(voice_file)
        print(f"      Voiceover duration: {voice_duration} seconds")
        
        rel_asset_path = os.path.relpath(gameplay_video, BASE_DIR).replace("\\", "/")
        
        final_scenes = [{
            "index": 1,
            "description": f"Gameplay Background Video: {gameplay_video.name}",
            "duration": voice_duration,
            "asset_path": rel_asset_path,
            "asset_type": "video"
        }]
        
        with open(scenes_file, "w", encoding="utf-8") as f:
            json.dump(final_scenes, f, indent=2, ensure_ascii=False)
            
        print(f"[06 Scene Planner] Saved gameplay scenes plan to: {scenes_file}")
        return final_scenes

    print(f"[06 Scene Planner] Parsing script visual instructions...")
    parsed_scenes = parse_scenes_and_durations(script_file)
    print(f"[06 Scene Planner] Identified {len(parsed_scenes)} scenes.")

    final_scenes = []
    
    for idx, scene in enumerate(parsed_scenes):
        scene_idx = idx + 1
        description = scene["description"]
        duration = scene["duration"]
        
        print(f"  Processing Scene {scene_idx}: '{description}' ({duration}s)")
        
        # Determine search keywords
        # Extract alphanumeric characters and clean up keywords
        clean_desc = re.sub(r'[^\w\s]', '', description)
        search_terms = " ".join(clean_desc.split()[:3])  # Keep first 3 words as search query
        
        asset_type = "image"
        asset_path = ""
        downloaded = False
        
        # Only query APIs if not in MOCK_PIPELINE
        if not MOCK_PIPELINE:
            # 1. Try Pexels Video
            video_path = output_dir / f"scene_{scene_idx:02d}.mp4"
            downloaded = download_pexels_video(search_terms, video_path)
            if downloaded:
                asset_path = f"outputs/{date_str}/scene_{scene_idx:02d}.mp4"
                asset_type = "video"
            
            # 2. Try Pixabay Image
            if not downloaded:
                image_path = output_dir / f"scene_{scene_idx:02d}.jpg"
                downloaded = download_pixabay_image(search_terms, image_path)
                if downloaded:
                    asset_path = f"outputs/{date_str}/scene_{scene_idx:02d}.jpg"
                    asset_type = "image"
                    
        # 3. Fallback: Local Pillow generated image
        if not downloaded:
            fallback_path = output_dir / f"scene_{scene_idx:02d}.png"
            asset_type = create_fallback_image(description, scene_idx, duration, fallback_path)
            asset_path = f"outputs/{date_str}/scene_{scene_idx:02d}.png"
            print(f"      Generated local stylized placeholder image.")

        final_scenes.append({
            "index": scene_idx,
            "description": description,
            "duration": duration,
            "asset_path": asset_path,
            "asset_type": asset_type
        })

    # Write scenes mapping to JSON
    with open(scenes_file, "w", encoding="utf-8") as f:
        json.dump(final_scenes, f, indent=2, ensure_ascii=False)

    print(f"[06 Scene Planner] Saved scenes plan to: {scenes_file}")
    return final_scenes

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plan scenes and fetch visual assets.")
    parser.add_argument(
        "--date",
        type=str,
        default=datetime.now().strftime("%Y-%m-%d"),
        help="Date directory name (YYYY-MM-DD). Defaults to today's date.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force replanning and asset download, overwriting any existing ones.",
    )
    args = parser.parse_args()

    try:
        scenes = plan_scenes(args.date, args.force)
        print(json.dumps(scenes, indent=2))
    except Exception as e:
        print(f"[ERROR] Step 06 Scene Planner failed: {e}", file=sys.stderr)
        sys.exit(1)
