import os
import sys
import json
import argparse
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from backend.config import get_output_dir, BASE_DIR

def generate_thumbnail(date_str: str, force: bool = False) -> None:
    output_dir = get_output_dir(date_str)
    topic_file = output_dir / "topic.json"
    scenes_file = output_dir / "scenes.json"
    thumbnail_file = output_dir / "thumbnail.png"

    if not topic_file.exists() or not scenes_file.exists():
        raise FileNotFoundError(f"Missing topic.json or scenes.json for {date_str}. Run previous steps first.")

    if thumbnail_file.exists() and not force:
        print(f"[09 Thumbnail] Thumbnail already exists at {thumbnail_file}. Skipping.")
        return

    # Load title and assets mapping
    with open(topic_file, "r", encoding="utf-8") as f:
        topic_data = json.load(f)
    with open(scenes_file, "r", encoding="utf-8") as f:
        scenes = json.load(f)

    title = topic_data.get("title", "FAILED TECH")
    
    # We want a punchy thumbnail text: split the title or make it shorter
    # e.g., if title is "The Strange History of the Dynasphere", make it "THE DYNASPHERE: WHY IT FAILED"
    # Let's clean and make a short version or just use the first 4-5 words in UPPERCASE.
    words = title.upper().split()
    thumbnail_text = " ".join(words[:4])
    if len(words) > 4:
         thumbnail_text += "\n" + " ".join(words[4:8])
    if len(words) > 8:
         thumbnail_text += "..."

    print(f"[09 Thumbnail] Generating template-based thumbnail for: '{title}'...")

    # Find the first image/visual asset to use as a background
    background_path = None
    for scene in scenes:
        asset_path = BASE_DIR / scene["asset_path"]
        if asset_path.exists():
            background_path = asset_path
            break

    # If background image is a PNG or JPG, open it; otherwise create a slate background
    width, height = 1080, 1920
    if background_path and background_path.suffix.lower() in (".png", ".jpg", ".jpeg"):
        try:
            bg_image = Image.open(background_path)
            
            # Crop background to 9:16 aspect ratio before resizing to prevent stretching
            bg_w, bg_h = bg_image.size
            target_aspect = 9 / 16
            current_aspect = bg_w / bg_h
            if current_aspect > target_aspect:
                new_w = int(bg_h * target_aspect)
                left = (bg_w - new_w) // 2
                bg_image = bg_image.crop((left, 0, left + new_w, bg_h))
            else:
                new_h = int(bg_w / target_aspect)
                top = (bg_h - new_h) // 2
                bg_image = bg_image.crop((0, top, bg_w, top + new_h))
                
            bg_image = bg_image.resize((width, height), Image.Resampling.LANCZOS)
        except Exception as e:
            print(f"[09 Thumbnail] [WARNING] Failed to load background asset: {e}. Using slate fallback.")
            bg_image = Image.new("RGB", (width, height), color=(30, 35, 45))
    else:
        bg_image = Image.new("RGB", (width, height), color=(30, 35, 45))

    # Create overlay for text contrast (dark semi-transparent layer in the center)
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    
    # Center dark overlay rectangle
    overlay_draw.rectangle([0, int(height * 0.35), width, int(height * 0.65)], fill=(0, 0, 0, 200))
    
    # Combine background and overlay
    final_image = Image.alpha_composite(bg_image.convert("RGBA"), overlay)
    draw = ImageDraw.Draw(final_image)

    # Drawing text
    # Pillow 10+ supports size parameter on load_default()
    try:
        font_title = ImageFont.load_default(size=56)
        font_sub = ImageFont.load_default(size=32)
    except TypeError:
        # Fallback for older Pillow versions
        font_title = ImageFont.load_default()
        font_sub = ImageFont.load_default()

    # Draw Category Tag centered
    draw.text((width // 2, int(height * 0.38)), "REDDIT STORIES", fill=(255, 70, 70), font=font_sub, anchor="mm")

    # Draw Title Text centered
    draw.text((width // 2, int(height * 0.48)), thumbnail_text, fill=(255, 255, 255), font=font_title, stroke_width=2, stroke_fill=(0, 0, 0), anchor="mm", align="center")

    # Draw subtitle/hook centered
    draw.text((width // 2, int(height * 0.58)), "AITA?", fill=(255, 215, 0), font=font_sub, stroke_width=1, stroke_fill=(0, 0, 0), anchor="mm")

    # Load series/episode from metadata if available
    metadata_file = output_dir / "metadata.json"
    series = None
    episode = None
    if metadata_file.exists():
        try:
            with open(metadata_file, "r", encoding="utf-8") as f:
                meta = json.load(f)
                series = meta.get("series")
                episode = meta.get("episode")
        except Exception:
            pass

    # Draw series/episode badge if series is provided
    if series:
        badge_text = f"{series} Ep. {episode}" if episode is not None else series
        badge_text = badge_text.upper()
        
        try:
            font_badge = ImageFont.load_default(size=24)
        except TypeError:
            font_badge = ImageFont.load_default()
            
        # Get text dimensions compatibly
        if hasattr(draw, "textbbox"):
            l, t, r, b = draw.textbbox((0, 0), badge_text, font=font_badge)
            text_w, text_h = r - l, b - t
        else:
            text_w, text_h = draw.textsize(badge_text, font=font_badge) if hasattr(draw, "textsize") else (len(badge_text) * 12, 24)
            
        badge_padding_x = 16
        badge_padding_y = 10
        badge_x = 50
        badge_y = 50
        
        box_x1 = badge_x
        box_y1 = badge_y
        box_x2 = badge_x + text_w + (badge_padding_x * 2)
        box_y2 = badge_y + text_h + (badge_padding_y * 2)
        
        # Draw transparent background box for badge on final_image (which is RGBA)
        overlay_badge = Image.new("RGBA", final_image.size, (0, 0, 0, 0))
        badge_draw = ImageDraw.Draw(overlay_badge)
        
        if hasattr(badge_draw, "rounded_rectangle"):
            badge_draw.rounded_rectangle([box_x1, box_y1, box_x2, box_y2], radius=8, fill=(30, 30, 30, 220), outline=(255, 70, 70, 255), width=2)
        else:
            badge_draw.rectangle([box_x1, box_y1, box_x2, box_y2], fill=(30, 30, 30, 220), outline=(255, 70, 70, 255), width=2)
            
        final_image = Image.alpha_composite(final_image, overlay_badge)
        draw = ImageDraw.Draw(final_image)
        
        # Draw badge text
        draw.text((badge_x + badge_padding_x, badge_y + badge_padding_y), badge_text, fill=(255, 255, 255), font=font_badge)

    # Save to dated output folder
    final_image.convert("RGB").save(thumbnail_file, "PNG")
    print(f"[09 Thumbnail] Successfully generated and saved thumbnail to: {thumbnail_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate YouTube video thumbnail.")
    parser.add_argument(
        "--date",
        type=str,
        default=datetime.now().strftime("%Y-%m-%d"),
        help="Date directory name (YYYY-MM-DD). Defaults to today's date.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force regeneration of the thumbnail, overwriting any existing one.",
    )
    args = parser.parse_args()

    try:
        generate_thumbnail(args.date, args.force)
    except Exception as e:
        print(f"[ERROR] Step 09 Thumbnail Generator failed: {e}", file=sys.stderr)
        sys.exit(1)
