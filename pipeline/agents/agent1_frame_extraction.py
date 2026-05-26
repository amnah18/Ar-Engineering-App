# agents/agent1_frame_extraction.py
# Rewritten to use Pillow only — no cv2, no scenedetect
# Works on any server including Streamlit Cloud

import os
from pathlib import Path
from PIL import Image, ImageStat
import imagehash

VIDEO_EXTS = {".mp4", ".mov"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png"}


def _phash(img: Image.Image):
    return imagehash.phash(img)


def _is_duplicate(new_hash, seen: list, threshold: int = 6) -> bool:
    return any(abs(new_hash - h) < threshold for h in seen)


def _extract_from_video(video_path: str, output_folder: str, seen_hashes: list, counter_start: int) -> list:
    """Extract frames from video using imageio — no cv2 needed."""
    print(f"\n[Agent 1] Video: {Path(video_path).name}")

    try:
        try:
            import imageio.v2 as iio  # type: ignore[import]
        except ImportError:
            import imageio as iio  # type: ignore[no-redef]
    except ImportError:
        raise RuntimeError("imageio not installed. Add 'imageio[ffmpeg]' to requirements.txt")

    saved = []
    counter = counter_start

    reader = iio.get_reader(video_path)
    try:
        fps = (reader.get_meta_data().get("fps") or 25)
        sample_every = max(1, int(fps * 5))

        for frame_idx, frame in enumerate(reader):
            if frame_idx % sample_every != 0:
                continue

            img = Image.fromarray(frame).convert("RGB")

            brightness = ImageStat.Stat(img.convert("L")).mean[0]
            if brightness < 40 or brightness > 220:
                continue

            h = _phash(img)
            if _is_duplicate(h, seen_hashes):
                continue

            seen_hashes.append(h)
            filename = f"frame_{counter:04d}_scene{frame_idx:06d}.jpg"
            filepath = os.path.join(output_folder, filename)
            img.save(filepath, "JPEG", quality=85)
            saved.append(filepath)
            counter += 1
            print(f"  Saved {filename}")
    finally:
        reader.close()

    return saved


def _copy_images(image_paths: list, output_folder: str, seen_hashes: list, counter_start: int) -> list:
    saved = []
    counter = counter_start

    for src in image_paths:
        try:
            img = Image.open(str(src)).convert("RGB")
        except Exception as e:
            print(f"  [Agent 1] Cannot read image, skipping: {src.name} — {e}")
            continue

        h = _phash(img)
        if _is_duplicate(h, seen_hashes):
            print(f"  [Agent 1] Duplicate, skipping: {src.name}")
            continue

        seen_hashes.append(h)
        filename = f"frame_{counter:04d}_{src.stem}.jpg"
        filepath = os.path.join(output_folder, filename)
        img.save(filepath, "JPEG", quality=85)
        saved.append(filepath)
        counter += 1
        print(f"  Copied {filename}")

    return saved


def process_input_folder(input_folder: str, output_frames_folder: str) -> list:
    os.makedirs(output_frames_folder, exist_ok=True)

    existing = sorted(Path(output_frames_folder).glob("*.jpg"))
    if existing:
        print(f"\n[Agent 1] Skipping — {len(existing)} frames already in {output_frames_folder}")
        return [str(f) for f in existing]

    input_path = Path(input_folder)
    videos = sorted(f for f in input_path.rglob("*") if f.suffix.lower() in VIDEO_EXTS)
    images = sorted(f for f in input_path.rglob("*") if f.suffix.lower() in IMAGE_EXTS)

    if not videos and not images:
        raise RuntimeError(f"No supported files found in {input_folder}")

    print(f"\n[Agent 1] Found {len(videos)} video(s), {len(images)} image(s)")

    seen_hashes = []
    all_frames = []

    for video in videos:
        frames = _extract_from_video(str(video), output_frames_folder, seen_hashes, len(all_frames))
        all_frames.extend(frames)

    if images:
        print(f"\n[Agent 1] Copying {len(images)} image(s)...")
        frames = _copy_images(images, output_frames_folder, seen_hashes, len(all_frames))
        all_frames.extend(frames)

    print(f"\n[Agent 1] Complete — {len(all_frames)} frames ready")
    return sorted(all_frames)


def extract_frames(video_path: str, output_folder: str) -> list:
    return _extract_from_video(video_path, output_folder, [], 0)
