# Standard-Stimmen vorbereiten und verteilen

Diese Anleitung beschreibt, wie du deine 25 Standard-Stimmen aus einem laufenden Docker-Container exportierst, im Repository versionierst und dafür sorgst, dass sie bei jeder Installation automatisch bereitstehen. Die Schritte funktionieren mit dem vorhandenen Setup unter Windows (PowerShell) sowie auf Linux-/macOS-Systemen.

## 1. Stimmen aus dem Container exportieren

1. Stelle sicher, dass der API-Container läuft. In deinem Setup heißt er `chatterbox-tts-api-uv-gpu`.
2. Öffne **PowerShell** im Projektstamm `C:\Users\Patrick\chatterbox`.
3. Exportiere den gemounteten Voice-Ordner des Containers:
   ```powershell
   mkdir C:\Users\Patrick\chatterbox\tmp-voices-export -Force | Out-Null
   docker cp chatterbox-tts-api-uv-gpu:/voices C:\Users\Patrick\chatterbox\tmp-voices-export
   ```
4. Kontrolliere den Export:
   ```powershell
   Get-ChildItem C:\Users\Patrick\chatterbox\tmp-voices-export
   ```
   Erwartet werden `voices.json`, optional `config.json` sowie alle Audiodateien (`.wav`, `.mp3`, `.flac`, ...).

> **Linux/macOS**: Verwende denselben `docker cp` Befehl, aber passe die Zielpfade an, z.\u202fB. `docker cp chatterbox-tts-api-uv-gpu:/voices ./tmp-voices-export`.

## 2. Dateien im Repository ablegen

1. Erstelle den versionierten Zielordner, falls noch nicht vorhanden:
   ```powershell
   New-Item -ItemType Directory -Path C:\Users\Patrick\chatterbox\chatterbox-tts-api\assets\default-voices -Force | Out-Null
   ```
2. Kopiere alle exportierten Dateien in das Repository:
   ```powershell
   Copy-Item -Path C:\Users\Patrick\chatterbox\tmp-voices-export\* `
             -Destination C:\Users\Patrick\chatterbox\chatterbox-tts-api\assets\default-voices `
             -Recurse -Force
   ```
3. Bereinige anschließend den temporären Ordner:
   ```powershell
   Remove-Item -Recurse -Force C:\Users\Patrick\chatterbox\tmp-voices-export
   ```

> **Hinweis:** Wenn du die Dateien direkt im Repository ergänzt (z.\u202fB. auf GitHub hochlädst), achte darauf, dass `assets/default-voices/voices.json` und alle 25 Audiodateien vollständig enthalten sind.

## 3. Metadaten prüfen

1. Öffne `assets/default-voices/voices.json` im Repository.
2. Jede Stimme benötigt mindestens folgende Felder:
   - `name`: Anzeigename der Stimme
   - `language`: ISO-Sprachcode (z.\u202fB. `de`, `en`, `fr`)
   - `filename`: Dateiname der Audiodatei (z.\u202fB. `maria_de.wav`)

   Der Seed-Mechanismus setzt `path` automatisch auf den endgültigen Speicherort. Falls das Feld vorhanden ist, reicht es, den Dateinamen einzutragen; der Pfad wird beim Kopieren überschrieben.

3. Optional kannst du weitere Felder wie `description`, `tags` oder model-spezifische Parameter ergänzen.

## 4. Änderungen committen und pushen

```powershell
cd C:\Users\Patrick\chatterbox\chatterbox-tts-api
git add assets\default-voices
git commit -m "Add default voice library"
git push
```

## 5. Ergebnis verifizieren

### Lokal

1. Lösche den Laufzeitordner (falls vorhanden):
   ```powershell
   Remove-Item -Recurse -Force C:\Users\Patrick\chatterbox\chatterbox-tts-api\voices
   ```
2. Führe das Seed-Modul aus oder starte die API:
   ```powershell
   cd C:\Users\Patrick\chatterbox\chatterbox-tts-api
   python -m app.core.voice_seed
   ```
3. Prüfe den Inhalt von `voices\voices.json` und kontrolliere, ob alle Dateien vorhanden sind.

### Docker

1. Baue die Images neu, damit die Assets eingebettet werden:
   ```powershell
   docker compose -f docker/docker-compose.uv.gpu.yml build --no-cache
   docker compose -f docker/docker-compose.uv.gpu.yml up -d
   ```
2. Kontrolliere den Zielordner im Container:
   ```powershell
   docker exec chatterbox-tts-api-uv-gpu ls /voices
   docker exec chatterbox-tts-api-uv-gpu cat /voices/voices.json
   ```

### API-Test

Sende eine Anfrage an `GET http://localhost:4123/v1/voices`. Die 25 Standard-Stimmen sollten inklusive Sprachcode angezeigt werden.

---

Sobald diese Schritte abgeschlossen sind, werden die Standard-Stimmen automatisch bei jeder lokalen Installation, jedem Docker-Start und jedem frischen Deployment bereitgestellt.
