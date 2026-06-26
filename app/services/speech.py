"""Локальная транскрибация голоса (faster-whisper, CPU)."""
from __future__ import annotations

import logging
import os
import tempfile
import threading
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

_model = None
_model_lock = threading.Lock()
_whisper_available: bool | None = None


def _ensure_ffmpeg() -> None:
    """Bundled ffmpeg from imageio-ffmpeg if system ffmpeg missing."""
    try:
        import imageio_ffmpeg

        exe = imageio_ffmpeg.get_ffmpeg_exe()
        ffmpeg_dir = str(Path(exe).parent)
        if ffmpeg_dir not in os.environ.get("PATH", ""):
            os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
    except Exception as exc:
        logger.debug("imageio-ffmpeg not available: %s", exc)


def whisper_ready() -> bool:
    global _whisper_available
    if not settings.whisper_enabled:
        return False
    if _whisper_available is not None:
        return _whisper_available
    try:
        import faster_whisper  # noqa: F401
        _whisper_available = True
    except ImportError:
        logger.warning("faster-whisper не установлен — голосовые отключены")
        _whisper_available = False
    return _whisper_available


def _cache_dir() -> str:
    root = os.getenv("DATA_ROOT", "D:/bars-support-bot-data")
    path = Path(root) / "whisper"
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


def _get_model():
    global _model
    if _model is not None:
        return _model
    with _model_lock:
        if _model is None:
            from faster_whisper import WhisperModel

            _ensure_ffmpeg()
            logger.info("Whisper: loading %s (CPU)...", settings.whisper_model)
            _model = WhisperModel(
                settings.whisper_model,
                device="cpu",
                compute_type="int8",
                download_root=_cache_dir(),
            )
            logger.info("Whisper model ready")
    return _model


def transcribe_bytes(audio_bytes: bytes, suffix: str = ".ogg") -> str:
    if not whisper_ready():
        raise RuntimeError(
            "Whisper недоступен. Установите: pip install faster-whisper "
            "(и ffmpeg в PATH для .ogg)"
        )
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes)
        path = tmp.name
    try:
        return transcribe_file(path)
    finally:
        Path(path).unlink(missing_ok=True)


def transcribe_file(path: str) -> str:
    model = _get_model()
    segments, _ = model.transcribe(
        path,
        language="ru",
        beam_size=1,
        vad_filter=True,
    )
    parts = [s.text.strip() for s in segments if s.text.strip()]
    return " ".join(parts).strip()


def warmup_whisper() -> None:
    if whisper_ready():
        _get_model()
