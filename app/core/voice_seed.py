"""Utilities to seed the runtime voice library with bundled default voices."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Dict, Tuple

from app.config import Config

# Supported audio extensions that should be copied into the runtime voice directory.
_AUDIO_EXTENSIONS: Tuple[str, ...] = (".wav", ".mp3", ".flac", ".ogg", ".m4a", ".opus")


def _get_repo_root() -> Path:
    """Return the repository root based on the current file location."""
    return Path(__file__).resolve().parents[2]


def _get_default_assets_dir() -> Path:
    """Return the path to the default voices directory inside the repository."""
    return _get_repo_root() / "assets" / "default-voices"


def _load_metadata(source_dir: Path) -> Dict:
    """Load voices metadata from the default assets directory."""
    metadata_file = source_dir / "voices.json"
    if not metadata_file.exists():
        raise FileNotFoundError(
            "voices.json nicht gefunden. Lege die Datei in assets/default-voices ab, bevor der Seed ausgeführt wird."
        )
    return json.loads(metadata_file.read_text(encoding="utf-8"))


def _copy_audio_files(source_dir: Path, target_dir: Path) -> None:
    """Copy supported audio files from the source directory to the runtime directory."""
    for file in source_dir.iterdir():
        if file.is_file() and file.suffix.lower() in _AUDIO_EXTENSIONS:
            shutil.copy2(file, target_dir / file.name)


def _copy_optional_config(source_dir: Path, target_dir: Path) -> None:
    """Copy config.json if it exists in the source directory."""
    config_src = source_dir / "config.json"
    if config_src.exists():
        shutil.copy2(config_src, target_dir / config_src.name)


def _ensure_target_dir() -> Path:
    """Ensure that the runtime voice directory exists and return it."""
    target_dir = Path(Config.VOICE_LIBRARY_DIR).expanduser().resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir


def _is_directory_populated(directory: Path) -> bool:
    """Return True if the directory already contains files."""
    return any(directory.iterdir())


def _update_metadata_paths(metadata: Dict, target_dir: Path) -> Dict:
    """Update the path entries inside the metadata to point to the runtime directory."""
    voices = metadata.get("voices", {})
    if not isinstance(voices, dict):
        raise ValueError("voices.json muss ein 'voices'-Objekt mit Einträgen enthalten.")

    for voice_key, entry in voices.items():
        if not isinstance(entry, dict):
            raise ValueError(f"Ungültiger Eintrag für Stimme '{voice_key}'.")

        filename = entry.get("filename")
        if not filename:
            existing_path = entry.get("path")
            if not existing_path:
                raise ValueError(
                    f"Eintrag '{voice_key}' muss mindestens 'filename' oder 'path' enthalten."
                )
            filename = Path(existing_path).name
            entry["filename"] = filename

        absolute_path = (target_dir / filename).resolve()
        entry["path"] = str(absolute_path)

    return metadata


def ensure_default_voices_seeded(force: bool = False) -> bool:
    """Copy bundled default voices into the runtime directory if necessary.

    Returns ``True`` wenn ein Seed durchgeführt wurde, andernfalls ``False``.
    ``force`` überschreibt bestehende Inhalte und kopiert die Dateien erneut.
    """

    source_dir = _get_default_assets_dir()
    if not source_dir.exists():
        print("[voice-seed] Kein assets/default-voices Ordner gefunden – Seed wird übersprungen.")
        return False

    target_dir = _ensure_target_dir()

    if not force and _is_directory_populated(target_dir):
        print(f"[voice-seed] Zielordner '{target_dir}' ist bereits befüllt – Seed wird übersprungen.")
        return False

    if force:
        for item in target_dir.iterdir():
            if item.is_file() or item.is_symlink():
                item.unlink()
            else:
                shutil.rmtree(item)

    try:
        metadata = _load_metadata(source_dir)
    except FileNotFoundError as exc:
        print(f"[voice-seed] {exc}")
        return False

    _copy_audio_files(source_dir, target_dir)
    _copy_optional_config(source_dir, target_dir)

    updated_metadata = _update_metadata_paths(metadata, target_dir)
    metadata_file = target_dir / "voices.json"
    metadata_file.write_text(
        json.dumps(updated_metadata, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"[voice-seed] {metadata_file} erfolgreich geschrieben.")
    return True


def main() -> None:
    """Command-line entry point for manual execution."""
    try:
        seeded = ensure_default_voices_seeded()
        if seeded:
            print("[voice-seed] Standard-Stimmen wurden bereitgestellt.")
        else:
            print("[voice-seed] Keine Aktion erforderlich.")
    except Exception as exc:  # pragma: no cover - CLI convenience
        print(f"[voice-seed] Fehler: {exc}")
        raise


if __name__ == "__main__":  # pragma: no cover - CLI convenience
    main()
