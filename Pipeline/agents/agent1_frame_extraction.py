# agents/agent1_frame_extraction.py
# Input:  folder containing any mix of .mp4, .mov, .jpg, .jpeg
# Output: flat folder of .jpg frames ready for Agent 2

import cv2
import os
from pathlib import Path

from PIL import Image
import imagehash
from scenedetect import open_video, SceneManager
from scenedetect.detectors import ContentDetector

VIDEO_EXTS = {".mp4", ".mov"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png"}


# ── Quality helpers ────────────────────────────────────────────────────────

def _sharpness(frame) -> float:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var()


def _brightness(frame) -> float:
    return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).mean()


def _phash(frame):
    img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    return imagehash.phash(img)


def _is_duplicate(new_hash, seen: list, threshold: int = 6) -> bool:
    return any(abs(new_hash - h) < threshold for h in seen)


# ── Video → frames ─────────────────────────────────────────────────────────

def _extract_from_video(video_path: str, output_folder: str, seen_hashes: list, counter_start: int) -> list:
    print(f"\n[Agent 1] Video: {Path(video_path).name}")

    video = open_video(video_path)
    scene_manager = SceneManager()
    scene_manager.add_detector(ContentDetector(threshold=27.0))
    scene_manager.detect_scenes(video)
    scenes = scene_manager.get_scene_list()

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    sample_points = (
        [((s.get_frames() + e.get_frames()) // 2) for s, e in scenes]
        if scenes else list(range(0, total_frames, int(fps * 5)))
    )

    saved = []
    counter = counter_start

    for scene_idx, base_frame in enumerate(sample_points):
        candidates = []

        for offset in [-15, -10, -5, 0, 5, 10, 15]:
            frame_num = max(0, base_frame + offset)
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
            ret, frame = cap.read()
            if not ret or frame is None:
                continue

            sharp = _sharpness(frame)
            bright = _brightness(frame)

            if sharp < 120 or bright < 40 or bright > 220:
                continue

            h = _phash(frame)
            if _is_duplicate(h, seen_hashes):
                continue

            candidates.append((sharp, frame_num, frame, h))

        if not candidates:
            cap.set(cv2.CAP_PROP_POS_FRAMES, base_frame)
            ret, frame = cap.read()
            if ret and frame is not None:
                candidates.append((0, base_frame, frame, _phash(frame)))

        candidates.sort(key=lambda x: x[0], reverse=True)

        for sharp, _, frame, h in candidates[:1]:
            if _is_duplicate(h, seen_hashes):
                continue
            seen_hashes.append(h)
            filename = f"frame_{counter:04d}_scene{scene_idx:03d}.jpg"
            filepath = os.path.join(output_folder, filename)
            cv2.imwrite(filepath, frame)
            saved.append(filepath)
            counter += 1
            print(f"  Saved {filename}  sharpness={sharp:.1f}")

    cap.release()
    return saved


# ── Image passthrough ──────────────────────────────────────────────────────

def _copy_images(image_paths: list, output_folder: str, seen_hashes: list, counter_start: int) -> list:
    saved = []
    counter = counter_start

    for src in image_paths:
        frame = cv2.imread(str(src))
        if frame is None:
            print(f"  [Agent 1] Cannot read image, skipping: {src.name}")
            continue

        h = _phash(frame)
        if _is_duplicate(h, seen_hashes):
            print(f"  [Agent 1] Duplicate, skipping: {src.name}")
            continue

        seen_hashes.append(h)
        filename = f"frame_{counter:04d}_{src.stem}.jpg"
        filepath = os.path.join(output_folder, filename)
        cv2.imwrite(filepath, frame)
        saved.append(filepath)
        counter += 1
        print(f"  Copied {filename}")

    return saved


# ── Main entry point ───────────────────────────────────────────────────────

def process_input_folder(input_folder: str, output_frames_folder: str) -> list:
    """
    Accepts a folder with any mix of .mp4, .mov, .jpg, .jpeg.
    Videos → scene-detected frames.
    Images → deduplicated and copied directly.
    Returns sorted list of all .jpg frame paths.
    """
    os.makedirs(output_frames_folder, exist_ok=True)

    existing = sorted(Path(output_frames_folder).glob("*.jpg"))
    if existing:
        print(f"\n[Agent 1] Skipping — {len(existing)} frames already in {output_frames_folder}")
        return [str(f) for f in existing]

    input_path = Path(input_folder)
    videos = sorted(f for f in input_path.rglob("*") if f.suffix.lower() in VIDEO_EXTS)
    images = sorted(f for f in input_path.rglob("*") if f.suffix.lower() in IMAGE_EXTS)

    if not videos and not images:
        raise RuntimeError(
            f"No .mp4, .mov, .jpg or .jpeg files found in {input_folder}"
        )

    print(f"\n[Agent 1] Found {len(videos)} video(s), {len(images)} image(s) in {input_folder}")

    seen_hashes: list = []
    all_frames: list = []

    for video in videos:
        frames = _extract_from_video(str(video), output_frames_folder, seen_hashes, len(all_frames))
        all_frames.extend(frames)

    if images:
        print(f"\n[Agent 1] Copying {len(images)} image(s)...")
        frames = _copy_images(images, output_frames_folder, seen_hashes, len(all_frames))
        all_frames.extend(frames)

    print(f"\n[Agent 1] Complete — {len(all_frames)} frames ready")
    return sorted(all_frames)


# kept for backwards compatibility with any direct callers
def extract_frames(video_path: str, output_folder: str) -> list:
    return _extract_from_video(video_path, output_folder, [], 0)
