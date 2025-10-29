import React from 'react';
import { Folder, Globe2, Languages, ListChecks, UploadCloud } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';

interface VoiceWorkflowGuideProps {
  isMultilingual: boolean;
  isLoadingLanguages: boolean;
  languageCount: number;
  voiceDirectoryPath?: string;
  hasVoices: boolean;
}

type StepStatus = 'success' | 'warning' | 'info';

interface WorkflowStep {
  id: number;
  title: string;
  description: React.ReactNode;
  status: StepStatus;
  icon: React.ComponentType<{ className?: string }>;
}

const statusColors: Record<StepStatus, string> = {
  success: 'text-emerald-600 dark:text-emerald-400',
  warning: 'text-amber-600 dark:text-amber-400',
  info: 'text-primary'
};

const statusBadges: Record<StepStatus, string> = {
  success: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-300',
  warning: 'bg-amber-500/10 text-amber-600 dark:text-amber-300',
  info: 'bg-primary/10 text-primary'
};

function StepBadge({ status, children }: { status: StepStatus; children: React.ReactNode }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-1 text-[11px] font-medium tracking-wide uppercase ${statusBadges[status]}`}
    >
      {children}
    </span>
  );
}

export default function VoiceWorkflowGuide({
  isMultilingual,
  isLoadingLanguages,
  languageCount,
  voiceDirectoryPath,
  hasVoices
}: VoiceWorkflowGuideProps) {
  const stepOneStatus: StepStatus = isMultilingual ? 'success' : 'warning';

  const steps: WorkflowStep[] = [
    {
      id: 1,
      title: 'Multilingual-Modus aktiv halten',
      description: (
        <div className="space-y-2 text-sm text-muted-foreground">
          <p>
            Setzen Sie <code className="font-mono text-xs">USE_MULTILINGUAL_MODEL=true</code> in Ihrer <code className="font-mono text-xs">.env</code>
            {' '}oder in den Docker-Variablen, damit alle 22 Sprachmodelle geladen werden.
          </p>
          <p>
            {isLoadingLanguages
              ? 'Der Server prüft aktuell die Sprachliste…'
              : isMultilingual
                ? `✅ ${languageCount} Sprachmodelle verfügbar – Voice-Uploader validiert Sprachcodes automatisch.`
                : '⚠️ Aktuell ist nur Englisch (en) aktiv. Aktivieren Sie den Multilingual-Modus, um weitere Sprachen freizuschalten.'}
          </p>
        </div>
      ),
      status: stepOneStatus,
      icon: Globe2
    },
    {
      id: 2,
      title: 'Persistenten Voice-Library-Pfad vorbereiten',
      description: (
        <div className="space-y-2 text-sm text-muted-foreground">
          <p>
            Legen Sie lokal ein Verzeichnis <code className="font-mono text-xs">voices/</code> an oder setzen Sie
            {' '}<code className="font-mono text-xs">VOICE_LIBRARY_DIR</code> auf einen versionskontrollierten Pfad.
            Dort speichert die API alle Audiodateien plus <code className="font-mono text-xs">voices.json</code>.
          </p>
          <pre className="rounded bg-muted p-3 text-xs leading-relaxed">
mkdir voices
# oder in Docker Compose / .env
VOICE_LIBRARY_DIR=./voices
          </pre>
          {voiceDirectoryPath && (
            <p className="text-xs">
              Aktueller Library-Pfad laut API: <code className="font-mono">{voiceDirectoryPath}</code>
            </p>
          )}
        </div>
      ),
      status: 'info',
      icon: Folder
    },
    {
      id: 3,
      title: 'Pro Sprache ein Voice-Sample hochladen',
      description: (
        <div className="space-y-2 text-sm text-muted-foreground">
          <p>
            Laden Sie für jede gewünschte Stimme ein Sample hoch. Nutzen Sie dafür diesen Assistenten oder die API direkt:
          </p>
          <pre className="rounded bg-muted p-3 text-xs leading-relaxed">
curl -X POST http://localhost:4123/v1/voices \
  -F "voice_name=de_maria" \
  -F "language=de" \
  -F "voice_file=@de_maria.wav"
          </pre>
          <p>
            Die Bibliothek validiert Dateiformat und Größe, legt das Sample im Voice-Verzeichnis ab und speichert Sprache plus Metadaten in
            {' '}<code className="font-mono text-xs">voices.json</code>.
          </p>
        </div>
      ),
      status: 'info',
      icon: UploadCloud
    },
    {
      id: 4,
      title: 'Ergebnis prüfen und versionieren',
      description: (
        <div className="space-y-2 text-sm text-muted-foreground">
          <p>
            Überprüfen Sie die Bibliothek mit <code className="font-mono text-xs">GET /v1/voices</code>. Nehmen Sie anschließend das komplette
            {' '}<code className="font-mono text-xs">voices/</code>-Verzeichnis (inkl. <code className="font-mono text-xs">voices.json</code>) ins Repository auf, um die Stimmen zu versionieren.
          </p>
          <p>
            {hasVoices
              ? '📦 Bereits hochgeladene Stimmen werden hier gelistet und können direkt validiert werden.'
              : 'Noch keine Stimmen vorhanden – fügen Sie oben ein erstes Sample hinzu.'}
          </p>
        </div>
      ),
      status: hasVoices ? 'success' : 'info',
      icon: ListChecks
    },
    {
      id: 5,
      title: 'Voice-Namen & Sprachwechsel steuern',
      description: (
        <div className="space-y-2 text-sm text-muted-foreground">
          <p>
            Verwenden Sie sprechende Bezeichner im Format <code className="font-mono text-xs">&lt;iso&gt;_&lt;beschreibung&gt;</code>, z. B.
            {' '}<code className="font-mono text-xs">de_maria</code> oder <code className="font-mono text-xs">nl_jan</code>.
          </p>
          <p>
            Bei jeder TTS-Anfrage übergeben Sie nur noch <code className="font-mono text-xs">voice</code>. Die API wählt automatisch die korrekte Sprache anhand des Namens aus.
          </p>
        </div>
      ),
      status: 'info',
      icon: Languages
    }
  ];

  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span>Workflow für neue Voices</span>
          <StepBadge status={stepOneStatus}>
            {isMultilingual ? 'Multilingual aktiv' : 'Aktion erforderlich'}
          </StepBadge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {steps.map((step) => {
          const Icon = step.icon;
          return (
            <div key={step.id} className="flex gap-4 rounded-lg border border-border/60 bg-muted/40 p-4">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-background shadow-inner">
                <Icon className={`h-5 w-5 ${statusColors[step.status]}`} />
              </div>
              <div className="space-y-2">
                <div className="flex flex-col gap-1">
                  <div className="flex items-center gap-3">
                    <span className="text-xs font-semibold text-muted-foreground">Schritt {step.id}</span>
                    <StepBadge status={step.status}>
                      {step.status === 'success' ? 'Erledigt' : step.status === 'warning' ? 'Bitte prüfen' : 'Info'}
                    </StepBadge>
                  </div>
                  <h3 className="text-sm font-semibold text-foreground">{step.title}</h3>
                </div>
                {step.description}
              </div>
            </div>
          );
        })}
        <div className="rounded-lg border border-dashed border-border/60 bg-background/60 p-4 text-xs text-muted-foreground">
          <p>
            💡 Tipp: Nutzen Sie die Voice Studio Oberfläche, um Uploads, Sprachen und Metadaten visuell zu pflegen. Alle Änderungen werden direkt in Ihrer persistenten Voice-Library gespeichert.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
