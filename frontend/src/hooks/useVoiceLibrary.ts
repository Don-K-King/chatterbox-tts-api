import { useState, useCallback, useMemo, useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { createTTSService } from '../services/tts';
import { useApiEndpoint } from './useApiEndpoint';
import type { VoiceSample, HealthResponse, VoiceLibraryResponse, SupportedLanguagesResponse } from '../types';
import { LANGUAGE_OPTIONS, DEFAULT_LANGUAGE, getLanguageByCode } from '../constants/languages';

// Convert backend voice data to frontend VoiceSample format
const convertToVoiceSample = (backendVoice: any): VoiceSample => {
  return {
    id: backendVoice.name, // Use name as ID for backend voices
    name: backendVoice.name,
    file: null as any, // We don't have the original File object for backend voices
    audioUrl: '', // We'll generate this on demand via download endpoint
    uploadDate: new Date(backendVoice.upload_date),
    aliases: backendVoice.aliases || [],
    language: backendVoice.language || 'en' // Default to English if not specified
  };
};

export function useVoiceLibrary() {
  const [selectedVoice, setSelectedVoice] = useState<VoiceSample | null>(null);
  const { apiBaseUrl } = useApiEndpoint();
  const queryClient = useQueryClient();

  const ttsService = useMemo(() => createTTSService(apiBaseUrl), [apiBaseUrl]);

  // Monitor backend health to know when it's ready
  const healthQuery = useQuery<HealthResponse>({
    queryKey: ['health', apiBaseUrl],
    queryFn: ttsService.getHealth,
    refetchInterval: 3000,
    retry: true,
    retryDelay: 1000,
    staleTime: 1000,
  });

  const languagesQuery = useQuery<SupportedLanguagesResponse>({
    queryKey: ['supported-languages', apiBaseUrl],
    queryFn: ttsService.getSupportedLanguages,
    enabled: healthQuery.data?.status === 'healthy' || healthQuery.data?.status === 'initializing',
    staleTime: 60000,
    retry: 2,
    refetchOnWindowFocus: false,
  });

  // Load voices from backend with dependency on health
  const voicesQuery = useQuery<VoiceSample[]>({
    queryKey: ['voices', apiBaseUrl],
    queryFn: async () => {
      const response: VoiceLibraryResponse = await ttsService.getVoices();
      const loadedVoices: VoiceSample[] = [];

      for (const backendVoice of response.voices) {
        const voiceSample = convertToVoiceSample(backendVoice);
        voiceSample.libraryPath = backendVoice.path;

        // Generate audio URL for preview (download endpoint)
        try {
          const audioBlob = await ttsService.downloadVoice(backendVoice.name);
          voiceSample.audioUrl = URL.createObjectURL(audioBlob);

          // Create a File object from the blob for compatibility
          voiceSample.file = new File([audioBlob], backendVoice.filename, {
            type: getAudioMimeType(backendVoice.file_extension)
          });
        } catch (error) {
          console.error(`Failed to load audio for voice ${backendVoice.name}:`, error);
          // Skip this voice if we can't load its audio
          continue;
        }

        loadedVoices.push(voiceSample);
      }

      return loadedVoices;
    },
    enabled: healthQuery.data?.status === 'healthy' || healthQuery.data?.status === 'initializing',
    retry: (failureCount, error: any) => {
      // Retry if the backend is still starting up or if it's a network error
      if (failureCount < 3) {
        const isNetworkError = error?.message?.includes('fetch') || error?.message?.includes('Failed to');
        const isServerError = error?.message?.includes('500') || error?.message?.includes('503');
        return isNetworkError || isServerError;
      }
      return false;
    },
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 3000),
    staleTime: 10000, // Cache for 10 seconds
    refetchOnWindowFocus: false,
  });

  const voices = voicesQuery.data || [];

  const languageOptions = useMemo(() => {
    if (languagesQuery.data?.languages?.length) {
      return languagesQuery.data.languages
        .map(language => {
          const knownLanguage = getLanguageByCode(language.code);
          const label = knownLanguage
            ? `${knownLanguage.flag ? `${knownLanguage.flag} ` : ''}${knownLanguage.name} (${knownLanguage.nativeName})`
            : `${language.code.toUpperCase()} – ${language.name}`;

          return {
            value: language.code,
            label,
            code: language.code,
            name: knownLanguage?.name ?? language.name
          };
        })
        .sort((a, b) => a.label.localeCompare(b.label));
    }

    return LANGUAGE_OPTIONS.map(option => ({
      ...option,
      code: option.value,
      name: option.label
    }));
  }, [languagesQuery.data]);

  const defaultLanguage = useMemo(() => {
    if (languagesQuery.data?.languages?.length) {
      return languagesQuery.data.languages.find(lang => lang.code === DEFAULT_LANGUAGE)?.code
        || languagesQuery.data.languages[0]?.code
        || DEFAULT_LANGUAGE;
    }
    return LANGUAGE_OPTIONS[0]?.value || DEFAULT_LANGUAGE;
  }, [languagesQuery.data]);

  const isMultilingual = useMemo(() => {
    if (languagesQuery.data?.model_type) {
      return languagesQuery.data.model_type === 'multilingual';
    }
    return languageOptions.length > 1;
  }, [languagesQuery.data, languageOptions.length]);

  // Cleanup URLs when voices change
  useEffect(() => {
    return () => {
      if (voicesQuery.data) {
        voicesQuery.data.forEach((voice: VoiceSample) => {
          if (voice.audioUrl) {
            URL.revokeObjectURL(voice.audioUrl);
          }
        });
      }
    };
  }, [voicesQuery.data]);

  const addVoice = useCallback(async (file: File, customName?: string, language?: string): Promise<VoiceSample> => {
    const voiceName = customName || file.name.replace(/\.[^/.]+$/, "");

    try {
      // Upload to backend
      await ttsService.uploadVoice(voiceName, file, language);

      // Create new voice sample
      const audioUrl = URL.createObjectURL(file);
      const voice: VoiceSample = {
        id: voiceName,
        name: voiceName,
        file,
        audioUrl,
        uploadDate: new Date(),
        aliases: [],
        language: language || 'en'
      };

      // Invalidate voices query to refetch the list
      queryClient.invalidateQueries({ queryKey: ['voices', apiBaseUrl] });

      return voice;
    } catch (error) {
      console.error('Error adding voice:', error);
      throw error;
    }
  }, [ttsService, queryClient, apiBaseUrl]);

  const deleteVoice = useCallback(async (voiceId: string) => {
    try {
      // Delete from backend
      await ttsService.deleteVoice(voiceId);

      const voice = voices.find((v: VoiceSample) => v.id === voiceId);
      if (voice && voice.audioUrl) {
        // Revoke URL
        URL.revokeObjectURL(voice.audioUrl);
      }

      // Clear selection if this voice was selected
      if (selectedVoice?.id === voiceId) {
        setSelectedVoice(null);
      }

      // Invalidate voices query to refetch the list
      queryClient.invalidateQueries({ queryKey: ['voices', apiBaseUrl] });
      // Also invalidate default voice query in case we deleted the default voice
      queryClient.invalidateQueries({ queryKey: ['default-voice', apiBaseUrl] });
    } catch (error) {
      console.error('Error deleting voice:', error);
      throw error;
    }
  }, [voices, selectedVoice, ttsService, queryClient, apiBaseUrl]);

  const renameVoice = useCallback(async (voiceId: string, newName: string) => {
    try {
      // Rename in backend
      await ttsService.renameVoice(voiceId, newName);

      // Update selected voice if it was the renamed one
      if (selectedVoice?.id === voiceId) {
        setSelectedVoice(prev => prev ? { ...prev, id: newName, name: newName } : null);
      }

      // Invalidate voices query to refetch the list
      queryClient.invalidateQueries({ queryKey: ['voices', apiBaseUrl] });
      // Also invalidate default voice query in case we renamed the default voice
      queryClient.invalidateQueries({ queryKey: ['default-voice', apiBaseUrl] });
    } catch (error) {
      console.error('Error renaming voice:', error);
      throw error;
    }
  }, [selectedVoice, ttsService, queryClient, apiBaseUrl]);

  const refreshVoices = useCallback(async () => {
    // Clean up existing URLs
    voices.forEach((voice: VoiceSample) => {
      if (voice.audioUrl) {
        URL.revokeObjectURL(voice.audioUrl);
      }
    });

    // Refetch voices
    await voicesQuery.refetch();
  }, [voicesQuery, voices]);

  const addAlias = useCallback(async (voiceName: string, alias: string) => {
    try {
      await ttsService.addAlias(voiceName, alias);

      // Invalidate voices query to refetch the list
      queryClient.invalidateQueries({ queryKey: ['voices', apiBaseUrl] });

      return true;
    } catch (error) {
      console.error('Error adding alias:', error);
      throw error;
    }
  }, [ttsService, queryClient, apiBaseUrl]);

  const removeAlias = useCallback(async (voiceName: string, alias: string) => {
    try {
      await ttsService.removeAlias(voiceName, alias);

      // Invalidate voices query to refetch the list
      queryClient.invalidateQueries({ queryKey: ['voices', apiBaseUrl] });

      return true;
    } catch (error) {
      console.error('Error removing alias:', error);
      throw error;
    }
  }, [ttsService, queryClient, apiBaseUrl]);

  return {
    voices,
    selectedVoice,
    setSelectedVoice,
    addVoice,
    deleteVoice,
    renameVoice,
    refreshVoices,
    addAlias,
    removeAlias,
    isLoading: voicesQuery.isLoading || healthQuery.isLoading,
    isBackendReady: healthQuery.data?.status === 'healthy' || healthQuery.data?.status === 'initializing',
    healthStatus: healthQuery.data?.status,
    error: voicesQuery.error,
    languageOptions,
    supportedLanguages: languagesQuery.data?.languages ?? [],
    defaultLanguage,
    isMultilingual,
    isLoadingLanguages: languagesQuery.isLoading,
    languagesError: languagesQuery.error
  };
}

// Helper function to get MIME type from file extension
function getAudioMimeType(extension: string): string {
  const mimeTypes: Record<string, string> = {
    '.mp3': 'audio/mpeg',
    '.wav': 'audio/wav',
    '.flac': 'audio/flac',
    '.m4a': 'audio/mp4',
    '.ogg': 'audio/ogg'
  };
  return mimeTypes[extension] || 'audio/mpeg';
} 