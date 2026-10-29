from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

from par.voice import tts


def test_empty_text_rejected() -> None:
    with pytest.raises(tts.TTSUnavailable):
        tts.synthesize_wav("   ")


@pytest.mark.skipif(sys.platform != "win32", reason="windows sapi only")
def test_silent_sapi_output_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class Proc:
        returncode = 0
        stdout = b""
        stderr = b""

    def fake_run(cmd, **_kw):  # type: ignore[no-untyped-def]
        script = Path(cmd[-1]).read_text(encoding="utf-8-sig")
        match = re.search(r"SetOutputToWaveFile\('(.+?)'\)", script)
        assert match, "template lost its output path"
        Path(match.group(1)).write_bytes(b"")  # SAPI produced nothing
        return Proc()

    monkeypatch.setattr(tts.subprocess, "run", fake_run)
    with pytest.raises(tts.TTSUnavailable, match="sapi_produced_no_audio"):
        tts.synthesize_wav("你好")
