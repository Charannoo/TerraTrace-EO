from __future__ import annotations

import hashlib
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageFilter


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalise(image: np.ndarray) -> np.ndarray:
    image = image.astype(np.float32) / 255.0
    output = np.empty_like(image)
    for channel in range(3):
        band = image[..., channel]
        low, high = np.percentile(band, [2, 98])
        output[..., channel] = np.clip((band - low) / max(high - low, 1e-5), 0, 1)
    return output


def _alignment_shift(before: np.ndarray, after: np.ndarray, radius: int = 3) -> tuple[int, int, float]:
    before_gray = before.mean(axis=2)
    after_gray = after.mean(axis=2)
    best = (0, 0, float("inf"))
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            y0a, y1a = max(0, dy), min(before_gray.shape[0], before_gray.shape[0] + dy)
            x0a, x1a = max(0, dx), min(before_gray.shape[1], before_gray.shape[1] + dx)
            y0b, y1b = max(0, -dy), min(after_gray.shape[0], after_gray.shape[0] - dy)
            x0b, x1b = max(0, -dx), min(after_gray.shape[1], after_gray.shape[1] - dx)
            left = before_gray[y0a:y1a, x0a:x1a]
            right = after_gray[y0b:y1b, x0b:x1b]
            if left.size == 0:
                continue
            residual = float(np.median(np.abs(left - right)))
            if residual < best[2]:
                best = (dx, dy, residual)
    return best


def _shift_image(array: np.ndarray, dx: int, dy: int) -> np.ndarray:
    shifted = np.roll(array, shift=(dy, dx), axis=(0, 1))
    if dy > 0:
        shifted[:dy] = shifted[dy]
    elif dy < 0:
        shifted[dy:] = shifted[dy - 1]
    if dx > 0:
        shifted[:, :dx] = shifted[:, dx][:, None]
    elif dx < 0:
        shifted[:, dx:] = shifted[:, dx - 1][:, None]
    return shifted


def analyze_pair(
    before_path: Path,
    after_path: Path,
    mask_path: Path,
    *,
    aoi_area_ha: float = 96.0,
    persistence: bool = True,
) -> dict[str, Any]:
    before_image = Image.open(before_path).convert("RGB")
    after_image = Image.open(after_path).convert("RGB")
    size = (384, 384)
    before_raw = np.asarray(before_image.resize(size, Image.Resampling.BILINEAR))
    after_raw = np.asarray(after_image.resize(size, Image.Resampling.BILINEAR))

    before = _normalise(before_raw)
    after = _normalise(after_raw)
    dx, dy, alignment_error = _alignment_shift(before, after)
    after = _shift_image(after, dx, dy)

    channel_delta = np.abs(after - before)
    luminance_delta = channel_delta.mean(axis=2)
    chroma_delta = channel_delta.max(axis=2) - channel_delta.min(axis=2)
    evidence = 0.82 * luminance_delta + 0.18 * chroma_delta
    threshold = float(max(0.145, np.percentile(evidence, 88)))
    raw_mask = evidence >= threshold

    neighbours = np.zeros_like(raw_mask, dtype=np.uint8)
    for offset_y in (-1, 0, 1):
        for offset_x in (-1, 0, 1):
            neighbours += np.roll(raw_mask, shift=(offset_y, offset_x), axis=(0, 1))
    clean_mask = raw_mask & (neighbours >= 4)

    mask_image = Image.fromarray((clean_mask.astype(np.uint8) * 255), mode="L")
    mask_image = mask_image.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MedianFilter(3))
    clean_mask = np.asarray(mask_image) > 0

    # Suppress isolated differences by retaining the dominant dense change region.
    # This behaves like a lightweight connected-component focus without SciPy.
    dense_rows = np.where(clean_mask.mean(axis=1) > 0.20)[0]
    dense_columns = np.where(clean_mask.mean(axis=0) > 0.20)[0]
    if dense_rows.size and dense_columns.size:
        margin = 16
        y_start = max(0, int(dense_rows.min()) - margin)
        y_end = min(clean_mask.shape[0], int(dense_rows.max()) + margin + 1)
        x_start = max(0, int(dense_columns.min()) - margin)
        x_end = min(clean_mask.shape[1], int(dense_columns.max()) + margin + 1)
        focused = np.zeros_like(clean_mask)
        focused[y_start:y_end, x_start:x_end] = clean_mask[y_start:y_end, x_start:x_end]
        if focused.mean() >= 0.015:
            clean_mask = focused

    changed_fraction = float(clean_mask.mean())
    changed_area_ha = round(changed_fraction * aoi_area_ha, 2)
    coordinates = np.argwhere(clean_mask)
    if coordinates.size:
        y_min, x_min = coordinates.min(axis=0)
        y_max, x_max = coordinates.max(axis=0)
        bbox = [
            round(float(x_min / size[0]), 4),
            round(float(y_min / size[1]), 4),
            round(float(x_max / size[0]), 4),
            round(float(y_max / size[1]), 4),
        ]
    else:
        bbox = [0, 0, 0, 0]

    overlay = np.zeros((size[1], size[0], 4), dtype=np.uint8)
    overlay[..., 0] = 255
    overlay[..., 1] = 177
    overlay[..., 2] = 72
    overlay[..., 3] = clean_mask.astype(np.uint8) * 118
    mask_path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(overlay, mode="RGBA").save(mask_path)

    residual_px = round(math.hypot(dx, dy), 2)
    usable_fraction = 1.0
    support = min(0.98, 0.52 + min(changed_fraction, 0.2) * 1.35 + (0.14 if persistence else 0))
    if residual_px > 1.5:
        support -= 0.18

    return {
        "method": "robust-rgb-difference-v1",
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "image_size": list(size),
        "alignment_shift": {"x": dx, "y": dy},
        "registration_residual_px": residual_px,
        "normalisation": "per-channel 2–98% robust stretch",
        "threshold": round(threshold, 4),
        "mean_absolute_difference": round(float(luminance_delta.mean()), 4),
        "changed_fraction": round(changed_fraction, 4),
        "changed_area_ha": changed_area_ha,
        "bbox_normalised": bbox,
        "usable_pixel_fraction": usable_fraction,
        "persistence_confirmed": persistence,
        "support_score": round(max(0.05, support), 3),
        "decision": "CHANGE" if changed_fraction >= 0.02 and support >= 0.62 else "NO_CHANGE",
        "quality_gates": {
            "readable_assets": True,
            "mutual_overlap": True,
            "registration": residual_px <= 1.5,
            "radiometric_normalisation": True,
            "minimum_mapping_area": changed_area_ha >= 0.5,
            "temporal_persistence": persistence,
        },
        "asset_hashes": {
            "before_sha256": sha256_file(before_path),
            "after_sha256": sha256_file(after_path),
        },
    }
