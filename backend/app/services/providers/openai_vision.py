from __future__ import annotations

import base64
from typing import Optional

from openai import OpenAI

from app.schemas import VisionResult
from app.services.ai_common import extract_json, normalize_vision_result


def analyze_openai(
    api_key: str,
    model: str,
    prompt: str,
    image_jpeg: bytes,
) -> VisionResult:
    client = OpenAI(api_key=api_key)
    b64 = base64.b64encode(image_jpeg).decode("ascii")
    response = client.chat.completions.create(
        model=model,
        temperature=0.1,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                    },
                ],
            }
        ],
    )
    content = response.choices[0].message.content or "{}"
    return normalize_vision_result(extract_json(content))
