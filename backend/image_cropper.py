from __future__ import annotations
"""
EduQuest Pro — Image Cropper Module
Provides smart cropping of question regions and visual diagrams/illustrations
from full exam page images based on normalized bounding boxes [ymin, xmin, ymax, xmax].
Includes automatic contour & whitespace refinement to trim question stem text lines
and encompass complete diagram bodies and attached labels/captions.
"""

import os
import io
import uuid
from typing import Optional, List, Tuple, Union
from PIL import Image

MEDIA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "media")
os.makedirs(MEDIA_DIR, exist_ok=True)


def refine_diagram_bbox(
    img: Image.Image,
    bbox: Union[List[float], Tuple[float, float, float, float]],
    dark_threshold: int = 185
) -> List[float]:
    """
    Intelligently refines a diagram bounding box:
    1. Removes any question stem text lines mistakenly included at the top.
    2. Extends downwards to capture all diagram labels/captions (e.g. 'Group 1 / Nhóm 1', 'Hình 1', etc.).
    3. Stops before answer options (A, B, C, D) below.
    4. Automatically frames X boundaries around the visual illustration with margin.
    Returns normalized bbox in scale 0..1000: [ymin, xmin, ymax, xmax].
    """
    try:
        W, H = img.size
        ymin, xmin, ymax, xmax = [float(v) for v in bbox]
        if max(ymin, xmin, ymax, xmax) <= 1.05:
            ymin *= 1000.0
            xmin *= 1000.0
            ymax *= 1000.0
            xmax *= 1000.0

        y1 = int(round(ymin * H / 1000.0))
        y2 = int(round(ymax * H / 1000.0))
        x1 = int(round(xmin * W / 1000.0))
        x2 = int(round(xmax * W / 1000.0))

        # Search window strictly controlled around the requested bbox
        sy1 = max(0, y1 - 25)
        sy2 = min(H, y2 + int(H * 0.08))
        sx1 = max(0, x1 - 30)
        sx2 = min(W, x2 + 30)

        gray = img.convert("L")

        # Row dark densities (subsampled by 2 horizontally for speed)
        row_dark = {}
        for y in range(sy1, sy2):
            d = sum(1 for x in range(sx1, sx2, 2) if gray.getpixel((x, y)) < dark_threshold)
            row_dark[y] = d

        # Segment rows into content blocks
        blocks = []
        in_block = False
        b_start = 0
        for y in range(sy1, sy2):
            is_dark = row_dark[y] > 5
            if is_dark and not in_block:
                in_block = True
                b_start = y
            elif not is_dark and in_block:
                in_block = False
                blocks.append((b_start, y - 1, y - b_start))
        if in_block:
            blocks.append((b_start, sy2 - 1, sy2 - b_start))

        if not blocks:
            return [ymin, xmin, ymax, xmax]

        # The diagram starts at the FIRST substantial block (height >= 35)
        # Any prior thin blocks (height <= 30) separated by whitespace are question stem text lines
        diag_blocks = []
        for b in blocks:
            if not diag_blocks:
                if b[2] >= 35:
                    diag_blocks.append(b)
            else:
                prev = diag_blocks[-1]
                gap = b[0] - prev[1]
                # Include closely attached caption/label (gap <= 25px, height <= 35px)
                # But stop before any separate options row (options rows are typically taller and separated)
                if gap <= 25 and b[2] <= 35:
                    diag_blocks.append(b)
                else:
                    break

        if not diag_blocks:
            # Fallback if no block had height >= 35 (e.g. thin single-line diagram)
            diag_blocks = [max(blocks, key=lambda b: b[2])]

        new_y1 = max(0, diag_blocks[0][0] - 6)
        new_y2 = min(H, diag_blocks[-1][1] + 6)

        # Refine X bounds within new_y1..new_y2
        active_x = []
        for x in range(sx1, sx2):
            d = sum(1 for y in range(new_y1, new_y2, 2) if gray.getpixel((x, y)) < dark_threshold)
            if d > 3:
                active_x.append(x)

        if active_x:
            new_x1 = max(0, min(active_x) - 10)
            new_x2 = min(W, max(active_x) + 10)
        else:
            new_x1, new_x2 = x1, x2

        return [
            round(new_y1 * 1000.0 / H, 1),
            round(new_x1 * 1000.0 / W, 1),
            round(new_y2 * 1000.0 / H, 1),
            round(new_x2 * 1000.0 / W, 1)
        ]
    except Exception as e:
        print(f"[refine_diagram_bbox] Error: {e}, falling back to original bbox")
        return [float(v) for v in bbox]


def crop_image_bbox(
    image_input: Union[str, bytes],
    bbox: Union[List[float], Tuple[float, float, float, float]],
    padding_pct: float = 0.01,
    output_prefix: str = "crop_diagram",
    auto_refine: bool = True
) -> Optional[str]:
    """
    Crops a sub-region from an image using normalized bounding box [ymin, xmin, ymax, xmax] (scale 0-1000 or 0.0-1.0).
    Optionally refines bounding box using contour/density analysis to strip question text and keep labels.
    Saves cropped image to data/media/<output_prefix>_<uuid>.png.
    Returns relative media path: '/media/<filename>.png', or None if invalid bbox.
    """
    if not bbox or len(bbox) != 4:
        return None

    try:
        if isinstance(image_input, str):
            if not os.path.exists(image_input):
                return None
            img = Image.open(image_input)
        elif isinstance(image_input, bytes):
            img = Image.open(io.BytesIO(image_input))
        else:
            return None

        # Auto-refine diagram bounding box
        target_bbox = bbox
        if auto_refine:
            target_bbox = refine_diagram_bbox(img, bbox)

        width, height = img.size
        ymin, xmin, ymax, xmax = [float(v) for v in target_bbox]

        # Determine if bbox is in 0..1 scale or 0..1000 scale
        if max(ymin, xmin, ymax, xmax) <= 1.05:
            norm_ymin, norm_xmin, norm_ymax, norm_xmax = ymin, xmin, ymax, xmax
        else:
            norm_ymin = ymin / 1000.0
            norm_xmin = xmin / 1000.0
            norm_ymax = ymax / 1000.0
            norm_xmax = xmax / 1000.0

        # Validate ordering
        if norm_ymin >= norm_ymax or norm_xmin >= norm_xmax:
            return None

        # Add optional margin/padding
        if padding_pct > 0:
            pad_y = (norm_ymax - norm_ymin) * padding_pct
            pad_x = (norm_xmax - norm_xmin) * padding_pct
            norm_ymin = max(0.0, norm_ymin - pad_y)
            norm_xmin = max(0.0, norm_xmin - pad_x)
            norm_ymax = min(1.0, norm_ymax + pad_y)
            norm_xmax = min(1.0, norm_xmax + pad_x)

        # Convert to absolute pixel coordinates
        px_x1 = int(round(norm_xmin * width))
        px_y1 = int(round(norm_ymin * height))
        px_x2 = int(round(norm_xmax * width))
        px_y2 = int(round(norm_ymax * height))

        # Check minimum dimension (at least 30x30 pixels)
        if (px_x2 - px_x1) < 30 or (px_y2 - px_y1) < 30:
            return None

        cropped = img.crop((px_x1, px_y1, px_x2, px_y2))
        
        # Save to MEDIA_DIR
        out_name = f"{output_prefix}_{uuid.uuid4().hex[:12]}.png"
        out_path = os.path.join(MEDIA_DIR, out_name)
        cropped.save(out_path, format="PNG", optimize=True)

        return f"/media/{out_name}"
    except Exception as e:
        print(f"[crop_image_bbox] Error cropping bbox {bbox}: {e}")
        return None
