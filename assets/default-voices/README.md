# Default Voice Assets

Dieser Ordner dient als versionierter Speicherort für die Standard-Stimmen der Chatterbox TTS API. Lege hier die Audiodateien (z.\u202fB. `*.wav`, `*.mp3`, `*.flac`) sowie die dazugehörige `voices.json` und optional `config.json` ab. Die Dateien werden beim ersten Start der Anwendung automatisch nach `VOICE_LIBRARY_DIR` (standardmäßig `./voices` bzw. `/voices` im Container) kopiert.

> **Wichtig:** Die eigentlichen Audiodateien werden im Produktionsbetrieb benötigt, sind aber nicht Bestandteil dieses Repositories. Folge der Anleitung in `docs/DEFAULT_VOICE_LIBRARY_SETUP.md`, um sie aus einem bestehenden Container zu exportieren und hier abzulegen.
