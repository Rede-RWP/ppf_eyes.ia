from __future__ import annotations

import os
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import quote, unquote, urlsplit, urlunsplit

import cv2
import numpy as np

from app.config import get_settings

# OpenCV/FFmpeg: prefer TCP for NVR/DVR reliability
os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")


def normalize_rtsp_url(url: str) -> str:
    """Percent-encode user/password so chars like # @ : / don't break the URL.

    Example: password 142536#DVR -> 142536%23DVR
    """
    url = (url or "").strip()
    if not url.lower().startswith("rtsp://"):
        return url

    # If password contains raw '#', urlsplit treats it as fragment — fix manually.
    body = url[7:]  # strip rtsp://
    if "@" in body:
        creds, hostpart = body.rsplit("@", 1)
        # hostpart may still include fragment if # was in password and path after
        # Handle: user:pass#frag@host OR user:pass@host/path#frag
        if ":" in creds:
            user, password = creds.split(":", 1)
        else:
            user, password = creds, ""

        # If # leaked into hostpart as fragment leftover from bad paste, ignore fragment
        if "#" in hostpart and "/" not in hostpart.split("#", 1)[0]:
            # rare malformed case — keep host before #
            hostpart = hostpart.split("#", 1)[0]

        user_enc = quote(unquote(user), safe="")
        pass_enc = quote(unquote(password), safe="")
        return f"rtsp://{user_enc}:{pass_enc}@{hostpart}"

    # No credentials — still strip accidental fragment
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))


def _capture_bgr_opencv(rtsp_url: str, timeout_sec: float):
    cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
    if not cap.isOpened():
        return False, "OpenCV não abriu o stream", None

    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    start = time.time()
    frame = None
    ok = False
    while time.time() - start < timeout_sec:
        ok, frame = cap.read()
        if ok and frame is not None:
            break
        time.sleep(0.15)
    cap.release()

    if not ok or frame is None:
        return False, "Timeout ao ler frame (OpenCV)", None
    return True, "Frame capturado", frame


def _bgr_to_jpeg(frame, quality: int = 85) -> Optional[bytes]:
    ok_enc, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok_enc:
        return None
    return buf.tobytes()


def _capture_with_ffmpeg(rtsp_url: str, timeout_sec: float = 15.0) -> Tuple[bool, str, Optional[bytes]]:
    """Fallback: grab one JPEG via ffmpeg CLI (more reliable with many NVRs)."""
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        out_path = tmp.name
    try:
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-rtsp_transport",
            "tcp",
            "-y",
            "-i",
            rtsp_url,
            "-frames:v",
            "1",
            "-q:v",
            "3",
            out_path,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec)
        path = Path(out_path)
        if proc.returncode != 0 or not path.exists() or path.stat().st_size < 100:
            err = (proc.stderr or proc.stdout or "ffmpeg falhou").strip()
            err = re.sub(r"\s+", " ", err)[:280]
            return False, f"ffmpeg: {err or 'não gerou frame'}", None
        return True, "Frame capturado (ffmpeg)", path.read_bytes()
    except subprocess.TimeoutExpired:
        return False, "Timeout ao capturar frame (ffmpeg)", None
    except FileNotFoundError:
        return False, "ffmpeg não encontrado no sistema", None
    finally:
        try:
            Path(out_path).unlink(missing_ok=True)
        except OSError:
            pass


def _hint_for_url(url: str, error: str) -> str:
    hints = []
    if "#" in url and "%23" not in url:
        hints.append("senha com # precisa ser codificada (%23) — o sistema já tenta corrigir")
    if "/Streaming/Channels/" in url:
        hints.append(
            "este NVR respondeu melhor com path tipo /h264/ch1/main/av_stream "
            "(ch1=câmera 1, ch2=câmera 2…)"
        )
    if "451" in error or "Parameter Not Understood" in error:
        hints.append("path RTSP provavelmente incorreto para este equipamento")
    if hints:
        return error + " | Dica: " + "; ".join(hints)
    return error


def capture_frame_bgr(
    rtsp_url: str, timeout_sec: float = 12.0
) -> Tuple[bool, str, Optional[object], Optional[bytes]]:
    """Captura frame BGR (numpy) + JPEG. Usado para movimento + IA."""
    normalized = normalize_rtsp_url(rtsp_url)
    ok, message, frame = _capture_bgr_opencv(normalized, timeout_sec)
    if ok and frame is not None:
        jpeg = _bgr_to_jpeg(frame)
        if jpeg:
            return True, message, frame, jpeg

    ok2, message2, data2 = _capture_with_ffmpeg(
        normalized, timeout_sec=max(timeout_sec, 15.0)
    )
    if ok2 and data2:
        arr = np.frombuffer(data2, dtype=np.uint8)
        bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        return True, message2, bgr, data2

    return False, _hint_for_url(rtsp_url, message2 or message), None, None


def capture_frame(rtsp_url: str, timeout_sec: float = 12.0) -> Tuple[bool, str, Optional[bytes]]:
    """Grab a single JPEG frame from an RTSP stream."""
    ok, message, _bgr, jpeg = capture_frame_bgr(rtsp_url, timeout_sec)
    return ok, message, jpeg


def save_jpeg(data: bytes, filename: str) -> str:
    settings = get_settings()
    settings.snapshots_path.mkdir(parents=True, exist_ok=True)
    path = settings.snapshots_path / filename
    path.write_bytes(data)
    return f"snapshots/{filename}"


def resolve_snapshot_path(relative: Optional[str]) -> Optional[Path]:
    if not relative:
        return None
    settings = get_settings()
    path = settings.data_path / relative
    if path.exists():
        return path
    return None
