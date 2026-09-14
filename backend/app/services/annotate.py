from __future__ import annotations

from io import BytesIO
from typing import Iterable, List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFont

from app.schemas import DetectionBox

# RGB
BOX_COLOR = (220, 40, 40)
LABEL_BG = (180, 20, 20)
LABEL_FG = (255, 255, 255)

LABEL_MAP = {
    "sem_touca": "Sem touca",
    "fardamento_inadequado": "Farda",
    "sem_epi": "Sem EPI",
    "celular": "Celular",
    "phone": "Celular",
    "phone_in_use": "Celular",
    "celular_excessivo": "Celular",
    "espera": "Espera",
    "waiting": "Espera",
    "people_waiting": "Espera",
    "tempo_espera_excessivo": "Espera",
    "pessoa": "Pessoa",
    "person": "Pessoa",
}


def _font(size: int) -> ImageFont.ImageFont:
    for path in (
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ):
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _pretty_label(raw: str, confidence: float) -> str:
    key = (raw or "pessoa").strip().lower()
    base = LABEL_MAP.get(key, raw.strip() if raw.strip() else "Pessoa")
    pct = int(round(max(0.0, min(1.0, confidence)) * 100))
    return f"{base} {pct}%"


def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


def _xyxy_pixels(
    box: Sequence[float], width: int, height: int
) -> Optional[Tuple[int, int, int, int]]:
    if len(box) < 4:
        return None
    x1, y1, x2, y2 = [_clamp01(v) for v in box[:4]]
    # accept xywh normalized if x2/y2 look like width/height (x1+x2<=1.2 etc.) — keep xyxy
    if x2 < x1:
        x1, x2 = x2, x1
    if y2 < y1:
        y1, y2 = y2, y1
    # If model returned absolute pixels by mistake
    if max(box) > 1.5:
        x1, y1, x2, y2 = [float(v) for v in box[:4]]
        if x2 < x1:
            x1, x2 = x2, x1
        if y2 < y1:
            y1, y2 = y2, y1
        left = int(max(0, min(width - 1, x1)))
        top = int(max(0, min(height - 1, y1)))
        right = int(max(left + 1, min(width - 1, x2)))
        bottom = int(max(top + 1, min(height - 1, y2)))
        return left, top, right, bottom

    left = int(x1 * width)
    top = int(y1 * height)
    right = int(x2 * width)
    bottom = int(y2 * height)
    if right - left < 4 or bottom - top < 4:
        return None
    left = max(0, min(width - 1, left))
    top = max(0, min(height - 1, top))
    right = max(left + 1, min(width - 1, right))
    bottom = max(top + 1, min(height - 1, bottom))
    return left, top, right, bottom


def filter_detections_for_alert(
    detections: Iterable[DetectionBox],
    *,
    violations: Sequence[str],
    phone_alert: bool = False,
    wait_alert: bool = False,
) -> List[DetectionBox]:
    """Pick boxes that match the alert reason; fall back to all flagged boxes."""
    dets = list(detections or [])
    if not dets:
        return []

    wanted = set(violations or [])
    if phone_alert:
        wanted.update({"celular", "phone", "phone_in_use", "celular_excessivo"})
    if wait_alert:
        wanted.update({"espera", "waiting", "people_waiting", "tempo_espera_excessivo"})

    matched = [d for d in dets if (d.label or "").lower() in wanted or d.flagged]
    if matched:
        return matched
    # Prefer flagged; else all
    flagged = [d for d in dets if d.flagged]
    return flagged or dets


def annotate_jpeg(
    jpeg: bytes,
    detections: Sequence[DetectionBox],
    *,
    quality: int = 90,
) -> bytes:
    if not detections:
        return jpeg
    img = Image.open(BytesIO(jpeg)).convert("RGB")
    draw = ImageDraw.Draw(img)
    w, h = img.size
    thickness = max(2, min(w, h) // 220)
    font_size = max(14, min(w, h) // 42)
    font = _font(font_size)

    for det in detections:
        coords = _xyxy_pixels(det.box, w, h)
        if not coords:
            continue
        left, top, right, bottom = coords
        for i in range(thickness):
            draw.rectangle(
                [left - i, top - i, right + i, bottom + i],
                outline=BOX_COLOR,
            )
        text = _pretty_label(det.label, det.confidence)
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        except Exception:  # noqa: BLE001
            tw, th = font.getsize(text) if hasattr(font, "getsize") else (len(text) * 8, 14)

        pad_x, pad_y = 6, 4
        label_h = th + pad_y * 2
        label_w = tw + pad_x * 2
        lx = left
        ly = top - label_h if top - label_h >= 0 else top
        if lx + label_w > w:
            lx = max(0, w - label_w)
        draw.rectangle([lx, ly, lx + label_w, ly + label_h], fill=LABEL_BG)
        draw.text((lx + pad_x, ly + pad_y - 1), text, fill=LABEL_FG, font=font)

    out = BytesIO()
    img.save(out, format="JPEG", quality=quality, optimize=True)
    return out.getvalue()
