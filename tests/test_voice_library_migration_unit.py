import json
from pathlib import Path

from app.config import Config
from app.core.voice_library import VoiceLibrary


def test_migrate_voice_updates_default_voice_path(tmp_path, monkeypatch):
    library_dir = tmp_path / "library"
    library_dir.mkdir()

    mp3_path = library_dir / "sample.mp3"
    mp3_path.write_bytes(b"dummy")

    metadata = {
        "voices": {
            "sample": {
                "name": "sample",
                "filename": "sample.mp3",
                "path": str(mp3_path),
                "file_extension": ".mp3",
                "original_extension": ".mp3",
                "aliases": [],
            }
        },
        "version": "2.1",
    }

    config = {
        "default_voice": "sample",
        "default_voice_path": str(mp3_path),
        "version": "1.1",
        "last_updated": None,
    }

    metadata_file = library_dir / "voices.json"
    metadata_file.write_text(json.dumps(metadata))
    config_file = library_dir / "config.json"
    config_file.write_text(json.dumps(config))

    wav_path = mp3_path.with_suffix(".wav")

    def fake_convert(self, source_path: Path) -> Path:
        assert source_path == mp3_path
        wav_path.write_bytes(b"converted")
        source_path.unlink(missing_ok=True)
        return wav_path

    monkeypatch.setattr(VoiceLibrary, "_convert_file_to_wav", fake_convert)

    original_voice_sample_path = Config.VOICE_SAMPLE_PATH
    Config.VOICE_SAMPLE_PATH = str(mp3_path)

    try:
        library = VoiceLibrary(library_dir=str(library_dir))

        assert Config.VOICE_SAMPLE_PATH == str(wav_path)
        assert library.get_default_voice_path() == str(wav_path)

        updated_metadata = json.loads(metadata_file.read_text())
        assert updated_metadata["voices"]["sample"]["path"] == str(wav_path)

        updated_config = json.loads(config_file.read_text())
        assert updated_config["default_voice_path"] == str(wav_path)
    finally:
        Config.VOICE_SAMPLE_PATH = original_voice_sample_path
