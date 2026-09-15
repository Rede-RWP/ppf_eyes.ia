from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import cv2
import numpy as np


@dataclass
class MotionResult:
    motion: bool
    score: float  # fração de pixels alterados 0–1
    baseline: bool  # True = primeiro frame (ainda sem comparação)


class MotionDetector:
    """Detecção leve por diferença de frames (grayscale + blur + absdiff)."""

    def __init__(self) -> None:
        self._prev: Dict[int, np.ndarray] = {}

    def reset(self, camera_id: int) -> None:
        self._prev.pop(camera_id, None)

    def detect(
        self,
        camera_id: int,
        frame_bgr: np.ndarray,
        *,
        sensitivity: float = 0.02,
        pixel_threshold: int = 25,
        max_width: int = 320,
    ) -> MotionResult:
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape[:2]
        if w > max_width:
            scale = max_width / float(w)
            gray = cv2.resize(
                gray,
                (max_width, max(1, int(h * scale))),
                interpolation=cv2.INTER_AREA,
            )
        gray = cv2.GaussianBlur(gray, (21, 21), 0)

        prev = self._prev.get(camera_id)
        self._prev[camera_id] = gray
        if prev is None or prev.shape != gray.shape:
            return MotionResult(motion=False, score=0.0, baseline=True)

        diff = cv2.absdiff(prev, gray)
        _, thresh = cv2.threshold(diff, int(pixel_threshold), 255, cv2.THRESH_BINARY)
        changed = float(np.count_nonzero(thresh))
        total = float(thresh.size) or 1.0
        score = changed / total
        return MotionResult(
            motion=score >= float(sensitivity),
            score=score,
            baseline=False,
        )


motion_detector = MotionDetector()
