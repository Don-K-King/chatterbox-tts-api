# Default Voice Assets

Dieser Ordner ist der versionierte Speicherort fuer die Standard-Stimmen der Chatterbox TTS API. Lege hier die Audiodateien (z. B. `*.wav`, `*.mp3`, `*.flac`) sowie die dazugehoerige `voices.json` und optional `config.json` ab. Die Dateien werden beim ersten Start der Anwendung automatisch nach `VOICE_LIBRARY_DIR` (standardmaessig `./voices` bzw. `/voices` im Container) kopiert.

Die Inhalte dieses Ordners sollen mit einem verifizierten Laufzeit-Container synchron gehalten werden, damit Deployments denselben Voice-Bestand wie die lokale Referenzumgebung erhalten. Wenn sich der Voice-Bestand im Container aendert, exportiere `/voices` erneut und aktualisiere diesen Ordner.
