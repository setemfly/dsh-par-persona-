"""Speech-to-text boundary.

v0 ships the interface and a clear failure mode instead of a fake microphone.
`FasterWhisperSTT` is opt-in (`pip install faster-whisper`) and stays out of the
default dependency set because it pulls in CTranslate2 and model weights.

Contract: return one transcript string; never invent audio content; if the model
is unavailable, raise STTUnavailable and let the UI degrade to typing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class STTUnavailable(RuntimeError):
    pass


class SpeechToText(Protocol):
    name: str

    def transcribe(self, wav_path: str | Path, *, language: str | None = None) -> str: ...


class NullSTT:
    name = "null"

    def transcribe(self, wav_path: str | Path, *, language: str | None = None) -> str:
        raise STTUnavailable("stt_not_configured: install the 'voice' extra")


class FasterWhisperSTT:
    name = "faster-whisper"

    def __init__(self, model_size: str = "small", device: str = "cpu") -> None:
        try:
            from faster_whisper import WhisperModel  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise STTUnavailable("faster_whisper_not_installed") from exc
        self._model = WhisperModel(model_size, device=device, compute_type="int8")

    def transcribe(self, wav_path: str | Path, *, language: str | None = None) -> str:
        segments, _ = self._model.transcribe(str(wav_path), language=language, vad_filter=True)
        return "".join(seg.text for seg in segments).strip()
