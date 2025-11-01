import asyncio
from types import SimpleNamespace

import torch
import pytest

from app.api.endpoints import speech


@pytest.fixture(autouse=True)
def restore_torchaudio(monkeypatch):
    original_ta = speech.ta
    yield
    speech.ta = original_ta


def test_ensure_wav_voice_sample_no_conversion(tmp_path, monkeypatch):
    wav_path = tmp_path / "prompt.wav"
    wav_path.write_bytes(b"WAVDATA")

    async def scenario():
        result = await speech.ensure_wav_voice_sample(str(wav_path))
        assert result == str(wav_path)
        assert wav_path.exists()

    asyncio.run(scenario())


def test_ensure_wav_voice_sample_converts(tmp_path, monkeypatch):
    mp3_path = tmp_path / "prompt.mp3"
    mp3_path.write_bytes(b"MP3DATA")

    wav_path = tmp_path / "prompt.wav"
    recorded = {}

    def fake_load(path):
        assert path == str(mp3_path)
        return torch.zeros(1, 10), 16000

    def fake_save(path, waveform, sample_rate, format="wav"):
        assert path == str(wav_path)
        assert format == "wav"
        wav_path.write_bytes(b"converted")
        recorded["saved"] = True

    async def fake_invalidate(path):
        recorded["invalidated"] = path

    monkeypatch.setattr(speech, "ta", SimpleNamespace(load=fake_load, save=fake_save))
    monkeypatch.setattr(speech, "invalidate_voice_prompt", fake_invalidate)

    async def scenario():
        result = await speech.ensure_wav_voice_sample(str(mp3_path))
        assert result == str(wav_path)
        assert not mp3_path.exists()
        assert wav_path.exists()
        assert recorded["saved"] is True
        assert recorded["invalidated"] == str(mp3_path)

    asyncio.run(scenario())
