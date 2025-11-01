"""Voice library management for storing and retrieving user-uploaded voices."""

from __future__ import annotations

import json
import hashlib
import logging
import os
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import torchaudio as ta

from app.config import Config

# Supported audio formats for voice uploads
SUPPORTED_VOICE_FORMATS = {".mp3", ".wav", ".flac", ".m4a", ".ogg"}

logger = logging.getLogger(__name__)


class VoiceLibrary:
    """Manages a library of voice samples for TTS generation."""

    def __init__(self, library_dir: Optional[str] = None) -> None:
        self.library_dir = Path(library_dir or Config.VOICE_LIBRARY_DIR)
        self.metadata_file = self.library_dir / "voices.json"
        self.config_file = self.library_dir / "config.json"
        self._ensure_library_dir()
        self._metadata = self._load_metadata()
        self._config = self._load_config()
        self._migrate_voice_storage()

    # ---------------------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------------------
    def _ensure_library_dir(self) -> None:
        """Ensure the voice library directory exists."""

        self.library_dir.mkdir(parents=True, exist_ok=True)

    def _load_metadata(self) -> Dict:
        """Load voice metadata from JSON file."""

        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, "r", encoding="utf-8") as file:
                    return json.load(file)
            except (json.JSONDecodeError, FileNotFoundError):
                logger.warning("Voice metadata file corrupted. Rebuilding metadata.")
        return {"voices": {}, "version": "2.1"}

    def _save_metadata(self) -> None:
        """Persist voice metadata to disk."""

        with open(self.metadata_file, "w", encoding="utf-8") as file:
            json.dump(self._metadata, file, indent=2, ensure_ascii=False)

    def _load_config(self) -> Dict:
        """Load configuration from JSON file."""

        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as file:
                    return json.load(file)
            except (json.JSONDecodeError, FileNotFoundError):
                logger.warning("Voice config file corrupted. Rebuilding configuration.")
        return {
            "default_voice": None,
            "default_voice_path": None,
            "version": "1.1",
            "last_updated": None,
        }

    def _save_config(self) -> None:
        """Persist configuration to disk."""

        self._config["last_updated"] = datetime.now().isoformat()
        with open(self.config_file, "w", encoding="utf-8") as file:
            json.dump(self._config, file, indent=2, ensure_ascii=False)

    @staticmethod
    def _get_file_hash(file_path: Path) -> str:
        """Generate a hash for the voice file for deduplication."""

        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as file:
            for chunk in iter(lambda: file.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def _convert_file_to_wav(self, source_path: Path) -> Path:
        """Convert an audio file to WAV format and return the new path."""

        if source_path.suffix.lower() == ".wav":
            return source_path

        wav_path = source_path.with_suffix(".wav")

        try:
            waveform, sample_rate = ta.load(str(source_path))
            ta.save(str(wav_path), waveform, sample_rate, format="wav")
        except Exception as exc:  # pragma: no cover - conversion is best-effort
            logger.error("Failed to convert %s to WAV: %s", source_path, exc)
            raise ValueError(f"Failed to convert voice sample to WAV: {exc}") from exc

        try:
            source_path.unlink(missing_ok=True)
        except Exception:  # pragma: no cover - clean-up errors are non-fatal
            logger.warning("Unable to delete original voice file %s after conversion", source_path)

        return wav_path

    def _migrate_voice_storage(self) -> None:
        """Ensure all stored voices are persisted as WAV files for optimal performance."""

        voices = self._metadata.get("voices", {})
        updated = False
        default_updated = False
        current_default_path = self._config.get("default_voice_path")

        for voice_name, metadata in list(voices.items()):
            voice_path = Path(metadata.get("path", ""))
            if not voice_path.exists():
                continue

            original_extension = metadata.get("original_extension") or metadata.get("file_extension", ".wav")

            if voice_path.suffix.lower() != ".wav":
                try:
                    wav_path = self._convert_file_to_wav(voice_path)
                except ValueError:
                    logger.warning("Skipping WAV migration for %s due to conversion failure", voice_name)
                    continue

                metadata["filename"] = wav_path.name
                metadata["file_extension"] = ".wav"
                metadata["path"] = str(wav_path)
                metadata["converted_from"] = voice_path.suffix.lower()
                metadata["original_extension"] = original_extension or voice_path.suffix.lower()
                metadata["converted_to_wav"] = True
                metadata["file_hash"] = self._get_file_hash(wav_path)
                updated = True

                if current_default_path and current_default_path == str(voice_path):
                    new_default_path = str(wav_path)
                    self._config["default_voice_path"] = new_default_path
                    if Config.VOICE_SAMPLE_PATH == str(voice_path):
                        Config.VOICE_SAMPLE_PATH = new_default_path
                    current_default_path = new_default_path
                    default_updated = True
            else:
                metadata.setdefault("converted_to_wav", False)
                metadata.setdefault("original_extension", original_extension)

            voices[voice_name] = metadata

        if updated:
            self._save_metadata()

        if default_updated:
            self._save_config()

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------
    def add_voice(self, voice_name: str, file_content: bytes, original_filename: str, language: str = "en") -> Dict:
        """Add a voice to the library."""

        if not voice_name or not voice_name.strip():
            raise ValueError("Voice name cannot be empty")

        voice_name = voice_name.strip()

        if not language or not language.strip():
            raise ValueError("Language code cannot be empty")

        language = language.strip().lower()

        invalid_chars = ["/", "\\", ":", "*", "?", '"', "<", ">", "|"]
        if any(char in voice_name for char in invalid_chars):
            raise ValueError(f"Voice name contains invalid characters: {invalid_chars}")

        file_ext = Path(original_filename).suffix.lower()
        if file_ext not in SUPPORTED_VOICE_FORMATS:
            raise ValueError(
                f"Unsupported file format: {file_ext}. Supported: {', '.join(sorted(SUPPORTED_VOICE_FORMATS))}"
            )

        if voice_name in self._metadata["voices"]:
            raise FileExistsError(f"Voice '{voice_name}' already exists")

        if self._get_voice_by_alias(voice_name) is not None:
            raise FileExistsError(f"Name '{voice_name}' is already used as an alias")

        # Persist original upload then convert to WAV for storage
        temp_path = self.library_dir / f"{voice_name}{file_ext}"
        with open(temp_path, "wb") as file:
            file.write(file_content)

        try:
            wav_path = self._convert_file_to_wav(temp_path)
        except ValueError:
            temp_path.unlink(missing_ok=True)
            raise

        file_hash = self._get_file_hash(wav_path)

        metadata = {
            "name": voice_name,
            "filename": wav_path.name,
            "original_filename": original_filename,
            "file_extension": ".wav",
            "original_extension": file_ext,
            "file_size": len(file_content),
            "file_hash": file_hash,
            "upload_date": datetime.now().isoformat(),
            "path": str(wav_path),
            "language": language,
            "aliases": [],
            "converted_to_wav": file_ext != ".wav",
            "converted_from": file_ext if file_ext != ".wav" else None,
        }

        self._metadata["voices"][voice_name] = metadata
        self._save_metadata()

        return metadata

    def get_voice_path(self, voice_name: str) -> Optional[str]:
        """Get the file path for a voice by name or alias."""

        if voice_name in self._metadata["voices"]:
            metadata = self._metadata["voices"][voice_name]
            voice_path = Path(metadata["path"])
            if not voice_path.exists():
                del self._metadata["voices"][voice_name]
                self._save_metadata()
                return None
            return str(voice_path)

        actual_name = self._get_voice_by_alias(voice_name)
        if actual_name:
            return self.get_voice_path(actual_name)
        return None

    def list_voices(self) -> List[Dict]:
        """List all voices in the library."""

        voices: List[Dict] = []
        removed: List[str] = []

        for voice_name, metadata in self._metadata.get("voices", {}).items():
            voice_path = Path(metadata.get("path", ""))
            if voice_path.exists():
                voice_data = {
                    **metadata,
                    "exists": True,
                    "aliases": metadata.get("aliases", []),
                    "language": metadata.get("language", "en"),
                    "original_extension": metadata.get("original_extension", metadata.get("file_extension", ".wav")),
                    "converted_to_wav": metadata.get("converted_to_wav", False),
                    "converted_from": metadata.get("converted_from"),
                }
                voices.append(voice_data)
            else:
                removed.append(voice_name)

        for voice_name in removed:
            del self._metadata["voices"][voice_name]

        if removed:
            self._save_metadata()

        voices.sort(key=lambda item: item.get("upload_date", ""), reverse=True)
        return voices

    def delete_voice(self, voice_name: str) -> bool:
        """Delete a voice from the library."""

        if voice_name not in self._metadata["voices"]:
            return False

        metadata = self._metadata["voices"][voice_name]
        voice_path = Path(metadata["path"])

        if voice_path.exists():
            try:
                voice_path.unlink()
            except OSError:
                logger.warning("Unable to delete voice file %s", voice_path)

        del self._metadata["voices"][voice_name]
        self._save_metadata()

        return True

    def rename_voice(self, old_name: str, new_name: str) -> bool:
        """Rename a voice."""

        if old_name not in self._metadata["voices"]:
            return False

        if not new_name or not new_name.strip():
            raise ValueError("Voice name cannot be empty")

        new_name = new_name.strip()

        invalid_chars = ["/", "\\", ":", "*", "?", '"', "<", ">", "|"]
        if any(char in new_name for char in invalid_chars):
            raise ValueError(f"Voice name contains invalid characters: {invalid_chars}")

        if new_name in self._metadata["voices"]:
            raise FileExistsError(f"Voice '{new_name}' already exists")

        metadata = self._metadata["voices"][old_name].copy()
        old_path = Path(metadata["path"])
        new_filename = f"{new_name}{metadata['file_extension']}"
        new_path = self.library_dir / new_filename

        if old_path.exists():
            try:
                old_path.rename(new_path)
            except OSError as exc:
                raise ValueError(f"Failed to rename voice file: {exc}") from exc

        metadata["name"] = new_name
        metadata["filename"] = new_filename
        metadata["path"] = str(new_path)

        self._metadata["voices"][new_name] = metadata
        del self._metadata["voices"][old_name]
        self._save_metadata()

        return True

    def get_voice_info(self, voice_name: str) -> Optional[Dict]:
        """Get detailed information about a voice by name or alias."""

        actual_name = self.resolve_voice_name(voice_name)
        if actual_name is None:
            return None

        metadata = self._metadata["voices"].get(actual_name)
        if metadata is None:
            return None

        voice_path = Path(metadata.get("path", ""))
        if not voice_path.exists():
            del self._metadata["voices"][actual_name]
            self._save_metadata()
            return None

        return {
            **metadata,
            "exists": True,
            "aliases": metadata.get("aliases", []),
            "converted_to_wav": metadata.get("converted_to_wav", False),
            "converted_from": metadata.get("converted_from"),
            "original_extension": metadata.get("original_extension", metadata.get("file_extension", ".wav")),
        }

    def cleanup_missing_files(self) -> List[str]:
        """Remove metadata entries for missing voice files."""

        removed: List[str] = []

        for voice_name, metadata in list(self._metadata.get("voices", {}).items()):
            voice_path = Path(metadata.get("path", ""))
            if not voice_path.exists():
                del self._metadata["voices"][voice_name]
                removed.append(voice_name)

        if removed:
            self._save_metadata()

        return removed

    def set_default_voice(self, voice_name: str) -> bool:
        """Set a voice from the library as the default voice."""

        voice_path = self.get_voice_path(voice_name)
        if voice_path is None:
            return False

        self._config["default_voice"] = voice_name
        self._config["default_voice_path"] = voice_path
        self._save_config()

        Config.VOICE_SAMPLE_PATH = voice_path

        return True

    def clear_default_voice(self) -> None:
        """Clear the default voice setting (revert to system default)."""

        original_path = os.getenv("VOICE_SAMPLE_PATH", "./voice-sample.mp3")

        self._config["default_voice"] = None
        self._config["default_voice_path"] = None
        self._save_config()

        Config.VOICE_SAMPLE_PATH = original_path

    def get_default_voice(self) -> Optional[str]:
        """Get the current default voice name."""

        return self._config.get("default_voice")

    def get_default_voice_path(self) -> Optional[str]:
        """Get the current default voice path."""

        stored_path = self._config.get("default_voice_path")
        if stored_path and Path(stored_path).exists():
            return stored_path
        return None

    def initialize_default_voice(self) -> None:
        """Initialize the default voice from persistent configuration on startup."""

        persistent_path = self.get_default_voice_path()
        if persistent_path:
            Config.VOICE_SAMPLE_PATH = persistent_path

    def _get_voice_by_alias(self, alias: str) -> Optional[str]:
        """Find the actual voice name by alias."""

        for voice_name, metadata in self._metadata.get("voices", {}).items():
            if alias in metadata.get("aliases", []):
                return voice_name
        return None

    def add_alias(self, voice_name: str, alias: str) -> bool:
        """Add an alias to a voice."""

        if voice_name not in self._metadata["voices"]:
            return False

        if not alias or not alias.strip():
            raise ValueError("Alias cannot be empty")

        alias = alias.strip()
        invalid_chars = ["/", "\\", ":", "*", "?", '"', "<", ">", "|"]
        if any(char in alias for char in invalid_chars):
            raise ValueError(f"Alias contains invalid characters: {invalid_chars}")

        if alias in self._metadata["voices"]:
            raise FileExistsError(f"Alias '{alias}' conflicts with existing voice name")

        existing_voice = self._get_voice_by_alias(alias)
        if existing_voice is not None and existing_voice != voice_name:
            raise FileExistsError(f"Alias '{alias}' already exists for voice '{existing_voice}'")

        aliases = self._metadata["voices"][voice_name].get("aliases", [])
        if alias not in aliases:
            aliases.append(alias)
            self._metadata["voices"][voice_name]["aliases"] = aliases
            self._save_metadata()

        return True

    def remove_alias(self, voice_name: str, alias: str) -> bool:
        """Remove an alias from a voice."""

        if voice_name not in self._metadata["voices"]:
            return False

        aliases = self._metadata["voices"][voice_name].get("aliases", [])
        if alias in aliases:
            aliases.remove(alias)
            self._metadata["voices"][voice_name]["aliases"] = aliases
            self._save_metadata()
            return True

        return False

    def list_aliases(self, voice_name: str) -> List[str]:
        """Get all aliases for a voice."""

        if voice_name not in self._metadata["voices"]:
            return []
        return self._metadata["voices"][voice_name].get("aliases", [])

    def get_all_voice_names(self) -> List[str]:
        """Get all voice names and aliases."""

        names = list(self._metadata.get("voices", {}).keys())
        for metadata in self._metadata.get("voices", {}).values():
            names.extend(metadata.get("aliases", []))
        return names

    def resolve_voice_name(self, name_or_alias: str) -> Optional[str]:
        """Resolve a name or alias to the actual voice name."""

        if name_or_alias in self._metadata.get("voices", {}):
            return name_or_alias
        return self._get_voice_by_alias(name_or_alias)

    def get_voice_language(self, voice_name: str) -> Optional[str]:
        """Get the language code for a voice by name or alias."""

        actual_name = self.resolve_voice_name(voice_name)
        if actual_name is None:
            return None

        metadata = self._metadata["voices"].get(actual_name)
        if metadata is None:
            return None

        return metadata.get("language", "en")

    def update_voice_language(self, voice_name: str, language: str) -> bool:
        """Update the language metadata for a voice."""

        actual_name = self.resolve_voice_name(voice_name)
        if actual_name is None:
            return False

        metadata = self._metadata["voices"].get(actual_name)
        if metadata is None:
            return False

        metadata["language"] = language
        self._metadata["voices"][actual_name] = metadata
        self._save_metadata()
        return True

    def export_library(self) -> Path:
        """Export the voice library (audio + metadata) as a ZIP archive."""

        voices = self.list_voices()
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        temp_dir = Path(tempfile.mkdtemp(prefix="voice-export-"))
        export_path = temp_dir / f"voice-library-{timestamp}.zip"

        export_metadata = {
            "generated_at": datetime.now().isoformat(),
            "voice_count": len(voices),
            "default_voice": self.get_default_voice(),
            "voices": [
                {
                    "name": voice["name"],
                    "filename": Path(voice["path"]).name,
                    "language": voice.get("language", "en"),
                    "aliases": voice.get("aliases", []),
                    "upload_date": voice.get("upload_date"),
                    "original_filename": voice.get("original_filename"),
                    "original_extension": voice.get("original_extension"),
                    "converted_to_wav": voice.get("converted_to_wav", False),
                    "converted_from": voice.get("converted_from"),
                    "file_hash": voice.get("file_hash"),
                }
                for voice in voices
                if Path(voice["path"]).exists()
            ],
        }

        with zipfile.ZipFile(export_path, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr("metadata.json", json.dumps(export_metadata, indent=2, ensure_ascii=False))
            for voice in voices:
                voice_path = Path(voice["path"])
                if not voice_path.exists():
                    continue
                arcname = Path("voices") / voice_path.name
                zip_file.write(voice_path, arcname=str(arcname))

        return export_path


# Global voice library instance
_voice_library: Optional[VoiceLibrary] = None


def get_voice_library() -> VoiceLibrary:
    """Get the global voice library instance."""

    global _voice_library
    if _voice_library is None:
        _voice_library = VoiceLibrary()
        _voice_library.initialize_default_voice()
    return _voice_library
