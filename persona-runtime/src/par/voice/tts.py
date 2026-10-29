"""Text-to-speech (Windows SAPI, offline).

Deliberately boring: synthesize a WAV through the OS voice, return bytes. No
cloud calls, no extra Python dependency, no always-on service. On non-Windows
hosts `synthesize_wav` raises TTSUnavailable and the UI says so.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path


class TTSUnavailable(RuntimeError):
    pass


_PS_TEMPLATE = r"""
Add-Type -AssemblyName System.Speech
$text = [System.IO.File]::ReadAllText('{text_path}', [System.Text.Encoding]::UTF8)
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
if ($text -match '[\u4e00-\u9fff]') {{
    $zh = $synth.GetInstalledVoices() | Where-Object {{ $_.Enabled -and $_.VoiceInfo.Culture.Name -like 'zh*' }} | Select-Object -First 1
    if ($zh) {{ $synth.SelectVoice($zh.VoiceInfo.Name) }}
}}
$synth.Rate = {rate}
$synth.Volume = {volume}
$synth.SetOutputToWaveFile('{wav_path}')
$synth.Speak($text)
$synth.Dispose()
"""


def synthesize_wav(text: str, *, rate: int = 0, volume: int = 100) -> bytes:
    if sys.platform != "win32":
        raise TTSUnavailable("windows_sapi_only")
    if not text.strip():
        raise TTSUnavailable("empty_text")
    # TMP may be relative or unset in some shells; resolve so PowerShell (which
    # may start in another cwd) still finds the files.
    tmp = Path(tempfile.mkdtemp(prefix="par_tts_")).resolve()
    token = uuid.uuid4().hex[:10]
    text_path = tmp / f"par_tts_{token}.txt"
    wav_path = tmp / f"par_tts_{token}.wav"
    script_path = tmp / f"par_tts_{token}.ps1"
    try:
        text_path.write_text(text[:1200], encoding="utf-8")
        script_path.write_text(
            _PS_TEMPLATE.format(
                text_path=str(text_path).replace("'", "''"),
                wav_path=str(wav_path).replace("'", "''"),
                rate=max(-10, min(10, rate)),
                volume=max(0, min(100, volume)),
            ),
            encoding="utf-8-sig",
        )
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(script_path)],
            capture_output=True,
            timeout=60,
            cwd=str(tmp),
        )
        if proc.returncode != 0 or not wav_path.exists():
            stderr = proc.stderr.decode("utf-8", "replace")[:300]
            raise TTSUnavailable(f"sapi_failed:{stderr}")
        data = wav_path.read_bytes()
        if len(data) < 44:  # smaller than a WAV header: speech never rendered
            raise TTSUnavailable("sapi_produced_no_audio:no_selectable_voice")
        return data
    finally:
        for p in (text_path, wav_path, script_path):
            try:
                os.unlink(p)
            except OSError:
                pass
        try:
            tmp.rmdir()
        except OSError:
            pass
