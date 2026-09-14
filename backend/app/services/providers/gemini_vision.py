from __future__ import annotations

import google.generativeai as genai

from app.schemas import VisionResult
from app.services.ai_common import extract_json, normalize_vision_result


def analyze_gemini(
    api_key: str,
    model: str,
    prompt: str,
    image_jpeg: bytes,
) -> VisionResult:
    genai.configure(api_key=api_key)
    vision = genai.GenerativeModel(model)
    response = vision.generate_content(
        [
            prompt,
            {"mime_type": "image/jpeg", "data": image_jpeg},
        ]
    )
    content = response.text or "{}"
    return normalize_vision_result(extract_json(content))
