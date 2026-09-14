from __future__ import annotations

import base64

from anthropic import Anthropic

from app.schemas import VisionResult
from app.services.ai_common import extract_json, normalize_vision_result


def analyze_claude(
    api_key: str,
    model: str,
    prompt: str,
    image_jpeg: bytes,
) -> VisionResult:
    client = Anthropic(api_key=api_key)
    b64 = base64.b64encode(image_jpeg).decode("ascii")
    response = client.messages.create(
        model=model,
        max_tokens=800,
        temperature=0.1,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": b64,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    )
    parts = []
    for block in response.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    content = "\n".join(parts) or "{}"
    return normalize_vision_result(extract_json(content))
