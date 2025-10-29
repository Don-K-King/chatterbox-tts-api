import React, { useMemo } from 'react';
import VoiceLibrary from '../components/VoiceLibrary';
import VoiceWorkflowGuide from '../components/voices/VoiceWorkflowGuide';
import VoiceDetailsPanel from '../components/voices/VoiceDetailsPanel';
import { useVoiceLibrary } from '../hooks/useVoiceLibrary';
import { useDefaultVoice } from '../hooks/useDefaultVoice';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { AlertTriangle, RefreshCcw } from 'lucide-react';

export default function VoiceStudioPage() {
  const {
    voices,
    selectedVoice,
    setSelectedVoice,
    addVoice,
    deleteVoice,
    renameVoice,
    refreshVoices,
    addAlias,
    removeAlias,
    isLoading: voicesLoading,
    error: voicesError,
    languageOptions,
    defaultLanguage: defaultUploadLanguage,
    isMultilingual,
    supportedLanguages,
    isLoadingLanguages,
  } = useVoiceLibrary();

  const {
    defaultVoice,
    updateDefaultVoice,
    clearDefaultVoice
  } = useDefaultVoice();

  const voiceDirectoryPath = useMemo(() => {
    const voiceWithPath = voices.find((voice) => voice.libraryPath);
    if (!voiceWithPath || !voiceWithPath.libraryPath) return undefined;
    const path = voiceWithPath.libraryPath;
    const separatorIndex = Math.max(path.lastIndexOf('/'), path.lastIndexOf('\\'));
    return separatorIndex >= 0 ? path.substring(0, separatorIndex) : path;
  }, [voices]);

  const hasVoices = voices.length > 0;

  const languageBadges = useMemo(() => {
    if (!supportedLanguages?.length) return null;
    return (
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {supportedLanguages.map((language) => (
          <div
            key={language.code}
            className="flex items-center justify-between rounded-md border border-border/60 bg-muted/40 px-3 py-2 text-xs"
          >
            <span className="font-medium text-foreground">{language.code.toUpperCase()}</span>
            <span className="text-muted-foreground">{language.name}</span>
          </div>
        ))}
      </div>
    );
  }, [supportedLanguages]);

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-6">
      <div className="space-y-2">
        <h1 className="text-2xl font-bold text-foreground">Voice Studio</h1>
        <p className="text-sm text-muted-foreground">
          Erstellen, validieren und versionieren Sie mehrsprachige Stimmen mit einem geführten Workflow. Jede Änderung wird in Ihrer persistenten Voice-Library gespeichert.
        </p>
      </div>

      {voicesError && !voicesLoading && (
        <div className="flex items-start gap-3 rounded-lg border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">
          <AlertTriangle className="mt-0.5 h-5 w-5" />
          <div className="space-y-1">
            <p className="font-semibold">Voice-Library konnte nicht geladen werden</p>
            <p>{voicesError instanceof Error ? voicesError.message : 'Unbekannter Fehler'}</p>
            <Button size="sm" variant="ghost" className="px-2" onClick={() => refreshVoices()}>
              <RefreshCcw className="mr-2 h-4 w-4" /> Erneut versuchen
            </Button>
          </div>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[1.2fr_1fr]">
        <VoiceWorkflowGuide
          isMultilingual={isMultilingual}
          isLoadingLanguages={isLoadingLanguages}
          languageCount={supportedLanguages?.length || 0}
          voiceDirectoryPath={voiceDirectoryPath}
          hasVoices={hasVoices}
        />

        <Card className="h-full">
          <CardHeader>
            <CardTitle>Aktive Sprachmodelle</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-baseline justify-between">
              <div>
                <p className="text-3xl font-semibold text-foreground">
                  {isLoadingLanguages ? '…' : supportedLanguages?.length ?? 0}
                </p>
                <p className="text-xs text-muted-foreground">verfügbare Sprachmodelle</p>
              </div>
              <div className="rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
                {isMultilingual ? 'Multilingual aktiv' : 'Standardmodus'}
              </div>
            </div>
            <p className="text-xs text-muted-foreground">
              Die Liste stammt direkt vom Server (<code className="font-mono text-[11px]">GET /v1/languages</code>). Nur validierte Sprachcodes können beim Upload ausgewählt werden.
            </p>
            <div className="max-h-64 space-y-3 overflow-y-auto pr-2">
              {isLoadingLanguages && (
                <div className="text-xs text-muted-foreground">Sprachen werden geladen…</div>
              )}
              {!isLoadingLanguages && languageBadges}
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.5fr_1fr]">
        <VoiceLibrary
          voices={voices}
          selectedVoice={selectedVoice}
          onVoiceSelect={setSelectedVoice}
          onAddVoice={addVoice}
          onDeleteVoice={deleteVoice}
          onRenameVoice={renameVoice}
          onRefresh={refreshVoices}
          isLoading={voicesLoading}
          defaultVoice={defaultVoice}
          onSetDefaultVoice={updateDefaultVoice}
          onClearDefaultVoice={clearDefaultVoice}
          onAddAlias={addAlias}
          onRemoveAlias={removeAlias}
          languageOptions={languageOptions}
          defaultLanguage={defaultUploadLanguage}
          isMultilingual={isMultilingual}
          isLoadingLanguages={isLoadingLanguages}
        />

        <VoiceDetailsPanel
          voice={selectedVoice}
          defaultVoice={defaultVoice}
          onSetDefaultVoice={updateDefaultVoice}
          onClearDefaultVoice={clearDefaultVoice}
          isMultilingual={isMultilingual}
        />
      </div>
    </div>
  );
}
