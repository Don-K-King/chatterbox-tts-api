import React from 'react';
import { BadgeCheck, Crown, Languages, Volume2 } from 'lucide-react';
import type { VoiceSample } from '../../types';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Button } from '../ui/button';
import { getLanguageFlag, getLanguageName } from '../../constants/languages';

interface VoiceDetailsPanelProps {
  voice: VoiceSample | null;
  defaultVoice?: string | null;
  onSetDefaultVoice?: (voiceName: string) => Promise<boolean>;
  onClearDefaultVoice?: () => Promise<boolean>;
  isMultilingual: boolean;
}

export default function VoiceDetailsPanel({
  voice,
  defaultVoice,
  onSetDefaultVoice,
  onClearDefaultVoice,
  isMultilingual
}: VoiceDetailsPanelProps) {
  const isDefault = voice && defaultVoice === voice.name;

  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle className="flex items-center gap-3">
          <span>Details &amp; Vorschau</span>
          {voice && (
            <span className="text-xs text-muted-foreground">{voice.name}</span>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {!voice && (
          <div className="flex h-full flex-col items-center justify-center gap-3 py-12 text-center text-muted-foreground">
            <Volume2 className="h-10 w-10 opacity-60" />
            <div>
              <p className="text-sm font-medium">Keine Stimme ausgewählt</p>
              <p className="text-xs">
                Wählen Sie eine Stimme in der Bibliothek aus, um Sprachcode, Sample und Aktionen zu sehen.
              </p>
            </div>
          </div>
        )}

        {voice && (
          <div className="space-y-6">
            <div className="rounded-lg border border-border/60 bg-muted/40 p-4">
              <div className="flex flex-col gap-2">
                <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
                  <Languages className="h-4 w-4" />
                  <span>Sprache</span>
                </div>
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <span className="text-lg">
                    {voice.language ? getLanguageFlag(voice.language) : '🌐'}
                  </span>
                  <span className="font-medium text-foreground">
                    {voice.language ? getLanguageName(voice.language) : 'Nicht angegeben'}
                  </span>
                  {isMultilingual ? (
                    <BadgeCheck className="h-4 w-4 text-emerald-500" title="Validierter Sprachcode" />
                  ) : (
                    <BadgeCheck className="h-4 w-4 text-muted-foreground" title="Standardmodus" />
                  )}
                </div>
                <p className="text-xs text-muted-foreground">
                  Sprachcodes folgen ISO-639-1 (z. B. de, en, nl). Nutzen Sie sprechende Voice-Namen wie <code className="font-mono">de_maria</code>.
                </p>
              </div>
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-semibold text-foreground">Sample anhören</span>
                {isDefault && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/10 px-2 py-1 text-[11px] font-semibold text-amber-600 dark:text-amber-300">
                    <Crown className="h-3 w-3" /> Standardstimme
                  </span>
                )}
              </div>
              <audio controls className="w-full">
                <source src={voice.audioUrl} />
                Ihr Browser unterstützt keine Audio-Wiedergabe.
              </audio>
              <p className="text-xs text-muted-foreground">
                Upload am {voice.uploadDate.toLocaleString()} – Datei {(voice.file.size / 1024 / 1024).toFixed(2)} MB
              </p>
            </div>

            {onSetDefaultVoice && (
              <div className="flex flex-wrap items-center gap-3">
                {!isDefault && (
                  <Button
                    size="sm"
                    onClick={() => onSetDefaultVoice(voice.name)}
                    className="inline-flex items-center gap-2"
                  >
                    <Crown className="h-4 w-4" /> Als Standard festlegen
                  </Button>
                )}
                {isDefault && onClearDefaultVoice && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => onClearDefaultVoice()}
                    className="inline-flex items-center gap-2"
                  >
                    <Crown className="h-4 w-4" /> Standard zurücksetzen
                  </Button>
                )}
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
