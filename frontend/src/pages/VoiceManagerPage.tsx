import React, { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Download, Loader2, Volume2 } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Textarea } from '../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import VoiceLibrary from '../components/VoiceLibrary';
import { createTTSService } from '../services/tts';
import { useApiEndpoint } from '../hooks/useApiEndpoint';
import { useVoiceLibrary } from '../hooks/useVoiceLibrary';
import { useDefaultVoice } from '../hooks/useDefaultVoice';
import { LANGUAGE_OPTIONS } from '../constants/languages';
import type { SupportedLanguageItem } from '../types';

const DEFAULT_TEST_TEXT = 'Hello! This is a quick test using the selected voice.';

export default function VoiceManagerPage() {
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
    updateVoiceLanguage,
    isLoading,
    isBackendReady,
    error
  } = useVoiceLibrary();

  const {
    defaultVoice,
    updateDefaultVoice,
    clearDefaultVoice
  } = useDefaultVoice();

  const { apiBaseUrl } = useApiEndpoint();
  const ttsService = useMemo(() => createTTSService(apiBaseUrl), [apiBaseUrl]);

  const [testText, setTestText] = useState(DEFAULT_TEST_TEXT);
  const [testVoiceId, setTestVoiceId] = useState<string | null>(null);
  const [testLanguage, setTestLanguage] = useState<string>('en');
  const [testAudioUrl, setTestAudioUrl] = useState<string | null>(null);
  const [isTesting, setIsTesting] = useState(false);
  const [testError, setTestError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  const { data: supportedLanguages } = useQuery({
    queryKey: ['supported-languages', apiBaseUrl],
    queryFn: async () => {
      const response = await ttsService.getSupportedLanguages();
      return response.languages;
    },
    staleTime: 1000 * 60 * 10,
  });

  useEffect(() => {
    if (selectedVoice) {
      setTestVoiceId(selectedVoice.id);
      if (selectedVoice.language) {
        setTestLanguage(selectedVoice.language);
      }
    }
  }, [selectedVoice]);

  useEffect(() => {
    if (!selectedVoice && voices.length > 0) {
      setSelectedVoice(voices[0]);
      setTestVoiceId(voices[0].id);
      if (voices[0].language) {
        setTestLanguage(voices[0].language);
      }
    } else if (voices.length === 0) {
      setTestVoiceId(null);
      setTestAudioUrl(null);
    }
  }, [voices, selectedVoice, setSelectedVoice]);

  useEffect(() => {
    return () => {
      if (testAudioUrl) {
        URL.revokeObjectURL(testAudioUrl);
      }
    };
  }, [testAudioUrl]);

  const availableLanguages: SupportedLanguageItem[] = supportedLanguages ?? LANGUAGE_OPTIONS.map(option => ({
    code: option.value,
    name: option.label
  }));

  const handleGenerateTest = async () => {
    if (!testVoiceId) {
      setTestError('Please select a voice to test.');
      return;
    }

    setTestError(null);
    setIsTesting(true);
    setTestAudioUrl(null);

    try {
      const blob = await ttsService.generateSpeech({
        input: testText,
        voice: testVoiceId,
        language: testLanguage,
      });
      const url = URL.createObjectURL(blob);
      setTestAudioUrl(url);
    } catch (err: any) {
      const message = err?.message || 'Failed to generate preview audio. Please try again.';
      setTestError(message);
    } finally {
      setIsTesting(false);
    }
  };

  const handleExport = async () => {
    setExportError(null);
    setExporting(true);
    try {
      const blob = await ttsService.exportVoices();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
      link.href = url;
      link.download = `voice-library-${timestamp}.zip`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (err: any) {
      const message = err?.message || 'Failed to export voice library. Please try again.';
      setExportError(message);
    } finally {
      setExporting(false);
    }
  };

  const languageOptions = availableLanguages.map(lang => ({
    value: lang.code,
    label: lang.name
  }));

  return (
    <div className="container mx-auto px-4 py-6 space-y-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-3xl font-bold">Voice Manager</h1>
          <p className="text-muted-foreground">
            Persistently manage your voice samples, update languages, and verify the output before using them via the API.
          </p>
          {!isBackendReady && (
            <p className="mt-2 text-sm text-amber-600 dark:text-amber-400">
              Backend initialising… voice data will appear automatically once the service is ready.
            </p>
          )}
          {error && (
            <p className="mt-2 text-sm text-destructive">{error instanceof Error ? error.message : 'Failed to load voices.'}</p>
          )}
        </div>
        <div className="flex flex-col items-stretch gap-2 sm:flex-row">
          {exportError && (
            <p className="text-sm text-destructive text-right sm:text-left">{exportError}</p>
          )}
          <Button
            variant="outline"
            onClick={handleExport}
            disabled={exporting || voices.length === 0}
            className="justify-center"
          >
            {exporting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                <span className="ml-2">Exporting…</span>
              </>
            ) : (
              <>
                <Download className="h-4 w-4" />
                <span className="ml-2">Export Voices</span>
              </>
            )}
          </Button>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
        <div className="space-y-6">
          <VoiceLibrary
            voices={voices}
            selectedVoice={selectedVoice}
            onVoiceSelect={setSelectedVoice}
            onAddVoice={addVoice}
            onDeleteVoice={deleteVoice}
            onRenameVoice={renameVoice}
            onRefresh={refreshVoices}
            isLoading={isLoading}
            defaultVoice={defaultVoice}
            onSetDefaultVoice={updateDefaultVoice}
            onClearDefaultVoice={clearDefaultVoice}
            onAddAlias={addAlias}
            onRemoveAlias={removeAlias}
            onUpdateLanguage={updateVoiceLanguage}
            canManage
          />
        </div>
        <Card className="h-fit">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <Volume2 className="h-5 w-5" />
              Voice Preview
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Voice</label>
              <Select
                value={testVoiceId ?? ''}
                onValueChange={(value) => setTestVoiceId(value)}
                disabled={voices.length === 0}
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder={voices.length === 0 ? 'No voices available' : 'Select a voice'} />
                </SelectTrigger>
                <SelectContent className="max-h-64">
                  {voices.map((voice) => (
                    <SelectItem key={voice.id} value={voice.id}>
                      {voice.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Test Language</label>
              <Select value={testLanguage} onValueChange={setTestLanguage}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select language" />
                </SelectTrigger>
                <SelectContent className="max-h-64">
                  {languageOptions.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                Select from supported languages to validate pronunciation. This will not change the saved language for the voice.
              </p>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Preview Text</label>
              <Textarea
                value={testText}
                onChange={(event) => setTestText(event.target.value)}
                rows={5}
              />
            </div>

            {testError && <p className="text-sm text-destructive">{testError}</p>}

            <div className="flex items-center gap-2">
              <Button onClick={handleGenerateTest} disabled={isTesting || !testVoiceId}>
                {isTesting ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span className="ml-2">Generating…</span>
                  </>
                ) : (
                  <>
                    <Volume2 className="h-4 w-4" />
                    <span className="ml-2">Test Voice</span>
                  </>
                )}
              </Button>
              <Button variant="outline" onClick={() => setTestText(DEFAULT_TEST_TEXT)} disabled={isTesting}>
                Reset Text
              </Button>
            </div>

            {testAudioUrl && (
              <div className="space-y-2">
                <p className="text-sm font-medium">Preview Result</p>
                <audio controls src={testAudioUrl} className="w-full">
                  Your browser does not support the audio element.
                </audio>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
