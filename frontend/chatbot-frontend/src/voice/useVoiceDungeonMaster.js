/* global globalThis */

import { useCallback, useEffect, useRef, useState } from 'react';
import { openAIRealtimeProvider } from './realtimeProvider';
import {
  isAssistantSpeechDoneEvent,
  isAssistantSpeechEvent,
  reduceTranscriptEvent,
} from './transcriptEvents';

export const VOICE_STATES = Object.freeze({
  IDLE: 'idle',
  CONNECTING: 'connecting',
  LISTENING: 'listening',
  SPEAKING: 'speaking',
  ERROR: 'error',
});

const AUDIO_LEVEL_INTERVAL_MS = 50;
const FALLBACK_PULSE_INTERVAL_MS = 120;
const FALLBACK_LEVELS = [0.34, 0.58, 0.42, 0.66];
const MAX_TOOL_ARGUMENTS_LENGTH = 32_768;
const MAX_TOOL_OUTPUT_LENGTH = 65_536;
const MAX_TOOL_JSON_NODES = 512;
const MAX_PROCESSED_TOOL_CALLS = 256;
const MAX_RESPONSE_REQUEST_KEYS = 512;
const UNSAFE_OBJECT_KEYS = new Set(['__proto__', 'prototype', 'constructor']);

function clampLevel(level) {
  return Math.max(0, Math.min(1, level));
}

export function parseBoundedToolArguments(argumentsJson) {
  if (
    typeof argumentsJson !== 'string' ||
    argumentsJson.length > MAX_TOOL_ARGUMENTS_LENGTH
  ) {
    throw new Error('Invalid tool arguments.');
  }
  const parsed = JSON.parse(argumentsJson);
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('Invalid tool arguments.');
  }

  const pending = [parsed];
  let visited = 0;
  while (pending.length) {
    const value = pending.pop();
    visited += 1;
    if (visited > MAX_TOOL_JSON_NODES) throw new Error('Invalid tool arguments.');
    Object.entries(value).forEach(([key, child]) => {
      if (UNSAFE_OBJECT_KEYS.has(key)) throw new Error('Invalid tool arguments.');
      if (child && typeof child === 'object') pending.push(child);
    });
  }
  return parsed;
}

function toolError(code, message) {
  return { ok: false, error: { code, message } };
}

function serializeToolOutput(output) {
  try {
    const serialized = JSON.stringify(output === undefined ? { ok: true } : output);
    if (
      typeof serialized !== 'string' ||
      serialized.length > MAX_TOOL_OUTPUT_LENGTH
    ) {
      return JSON.stringify(
        toolError('tool_output_invalid', 'The tool result was too large.'),
      );
    }
    return serialized;
  } catch (_error) {
    return JSON.stringify(
      toolError('tool_output_invalid', 'The tool result could not be serialized.'),
    );
  }
}

function completedToolCalls(event) {
  if (event?.type !== 'response.done' || !Array.isArray(event.response?.output)) {
    return [];
  }
  return event.response.output
    .filter((item) => item?.type === 'function_call' && item.status === 'completed')
    .map((item) => ({
      name: item.name,
      argumentsJson: item.arguments,
      callId: item.call_id,
    }));
}

function realtimeEventErrorMessage(event) {
  const rawCode = event?.error?.code;
  const rawMessage = event?.error?.message;
  const code = typeof rawCode === 'string'
    ? rawCode.replace(/[^A-Za-z0-9._:-]/g, '').slice(0, 96)
    : '';
  const message = typeof rawMessage === 'string'
    ? Array.from(rawMessage)
      .map((character) => {
        const codePoint = character.charCodeAt(0);
        return codePoint < 32 || codePoint === 127 ? ' ' : character;
      })
      .join('')
      .trim()
      .slice(0, 360)
    : '';
  if (code && message) return `Voice service error (${code}): ${message}`;
  if (message) return `Voice service error: ${message}`;
  if (code) return `Voice service error (${code}).`;
  return 'The voice service reported an error.';
}

/**
 * Start a throttled RMS meter over the remote stream. Returns null when the
 * Web Audio API is unavailable so callers can use a visual pulse fallback.
 */
export function startRemoteAudioLevelMonitor(stream, onLevel) {
  const AudioContextImpl =
    globalThis.AudioContext || globalThis.webkitAudioContext;
  const requestFrame = globalThis.requestAnimationFrame?.bind(globalThis);
  const cancelFrame = globalThis.cancelAnimationFrame?.bind(globalThis);
  if (!AudioContextImpl || !requestFrame || !cancelFrame || !stream) return null;

  let audioContext;
  let source;
  let analyser;
  let frameId;
  let stopped = false;
  let lastSampleAt = -Infinity;

  try {
    audioContext = new AudioContextImpl();
    analyser = audioContext.createAnalyser();
    analyser.fftSize = 256;
    analyser.smoothingTimeConstant = 0.65;
    source = audioContext.createMediaStreamSource(stream);
    source.connect(analyser);
  } catch (_error) {
    source?.disconnect?.();
    audioContext?.close?.();
    return null;
  }

  const samples = new Uint8Array(analyser.fftSize);
  const sample = (timestamp) => {
    if (stopped) return;
    if (timestamp - lastSampleAt >= AUDIO_LEVEL_INTERVAL_MS) {
      analyser.getByteTimeDomainData(samples);
      let sumOfSquares = 0;
      samples.forEach((sampleValue) => {
        const centered = (sampleValue - 128) / 128;
        sumOfSquares += centered * centered;
      });
      const rms = Math.sqrt(sumOfSquares / samples.length);
      onLevel(clampLevel(rms * 3.2));
      lastSampleAt = timestamp;
    }
    frameId = requestFrame(sample);
  };
  frameId = requestFrame(sample);

  return () => {
    if (stopped) return;
    stopped = true;
    cancelFrame(frameId);
    source?.disconnect?.();
    analyser?.disconnect?.();
    audioContext?.close?.();
  };
}

function publicError(error) {
  if (error && typeof error.message === 'string' && error.message) return error;
  return new Error('The voice connection encountered an unexpected error.');
}

export function useVoiceDungeonMaster({
  provider = openAIRealtimeProvider,
  autoConnect = false,
  initialMuted = true,
  onStateChange,
  onSpeakingChange,
  onTranscript,
  onAudioLevel,
  onError,
  onEvent,
  onToolCall,
} = {}) {
  const startsMuted = Boolean(initialMuted);
  const [status, setStatus] = useState(VOICE_STATES.IDLE);
  const [muted, setMutedState] = useState(startsMuted);
  const [transcript, setTranscript] = useState([]);
  const [error, setError] = useState(null);
  const transcriptRef = useRef([]);
  const connectionRef = useRef(null);
  const connectingRef = useRef(false);
  const connectAttemptRef = useRef(0);
  const mountedRef = useRef(true);
  const callbacksRef = useRef({});
  const audioMonitorCleanupRef = useRef(null);
  const hasAudioMonitorRef = useRef(false);
  const fallbackPulseRef = useRef(null);
  const speakingRef = useRef(false);
  const processedToolCallsRef = useRef(new Set());
  const responseActiveRef = useRef(false);
  const toolExecutionsRef = useRef(0);
  const pendingResponseRequestsRef = useRef(new Map());
  const completedResponseRequestsRef = useRef(new Set());
  const responseRequestSequenceRef = useRef(0);
  const responseSchedulerGenerationRef = useRef(0);

  callbacksRef.current = {
    onStateChange,
    onSpeakingChange,
    onTranscript,
    onAudioLevel,
    onError,
    onEvent,
    onToolCall,
  };

  const emitAudioLevel = useCallback((level) => {
    callbacksRef.current.onAudioLevel?.(clampLevel(level));
  }, []);

  const stopFallbackPulse = useCallback(() => {
    if (fallbackPulseRef.current) {
      clearInterval(fallbackPulseRef.current);
      fallbackPulseRef.current = null;
    }
    emitAudioLevel(0);
  }, [emitAudioLevel]);

  const startFallbackPulse = useCallback(() => {
    if (
      hasAudioMonitorRef.current ||
      fallbackPulseRef.current ||
      !callbacksRef.current.onAudioLevel
    ) {
      return;
    }
    let pulseIndex = 0;
    emitAudioLevel(FALLBACK_LEVELS[pulseIndex]);
    fallbackPulseRef.current = setInterval(() => {
      pulseIndex = (pulseIndex + 1) % FALLBACK_LEVELS.length;
      emitAudioLevel(FALLBACK_LEVELS[pulseIndex]);
    }, FALLBACK_PULSE_INTERVAL_MS);
  }, [emitAudioLevel]);

  const transition = useCallback((nextStatus) => {
    if (!mountedRef.current) return;
    setStatus(nextStatus);
    callbacksRef.current.onStateChange?.(nextStatus);
  }, []);

  const setSpeaking = useCallback(
    (speaking) => {
      if (speakingRef.current === speaking) return;
      speakingRef.current = speaking;
      callbacksRef.current.onSpeakingChange?.(speaking);
      if (speaking) {
        transition(VOICE_STATES.SPEAKING);
        startFallbackPulse();
      } else {
        stopFallbackPulse();
        if (connectionRef.current) transition(VOICE_STATES.LISTENING);
      }
    },
    [startFallbackPulse, stopFallbackPulse, transition],
  );

  const stopAudioMonitor = useCallback(() => {
    audioMonitorCleanupRef.current?.();
    audioMonitorCleanupRef.current = null;
    hasAudioMonitorRef.current = false;
  }, []);

  const handleRemoteStream = useCallback(
    (stream) => {
      stopAudioMonitor();
      if (!callbacksRef.current.onAudioLevel) return;
      const cleanup = startRemoteAudioLevelMonitor(stream, emitAudioLevel);
      if (cleanup) {
        stopFallbackPulse();
        audioMonitorCleanupRef.current = cleanup;
        hasAudioMonitorRef.current = true;
      } else if (speakingRef.current) {
        startFallbackPulse();
      }
    },
    [emitAudioLevel, startFallbackPulse, stopAudioMonitor, stopFallbackPulse],
  );

  const resetResponseScheduler = useCallback(() => {
    responseSchedulerGenerationRef.current += 1;
    responseActiveRef.current = false;
    toolExecutionsRef.current = 0;
    pendingResponseRequestsRef.current.clear();
    completedResponseRequestsRef.current.clear();
    responseRequestSequenceRef.current = 0;
  }, []);

  const failSession = useCallback(
    (message) => {
      connectAttemptRef.current += 1;
      connectingRef.current = false;
      const failedConnection = connectionRef.current;
      connectionRef.current = null;
      resetResponseScheduler();
      failedConnection?.disconnect?.();
      stopAudioMonitor();
      setSpeaking(false);
      stopFallbackPulse();
      const sessionError = new Error(message);
      setError(sessionError);
      callbacksRef.current.onError?.(sessionError);
      transition(VOICE_STATES.ERROR);
    },
    [resetResponseScheduler, setSpeaking, stopAudioMonitor, stopFallbackPulse, transition],
  );

  const sendRawEvent = useCallback((event) => {
    if (
      !event ||
      typeof event !== 'object' ||
      typeof connectionRef.current?.sendEvent !== 'function'
    ) {
      return false;
    }
    try {
      connectionRef.current.sendEvent(event);
      return true;
    } catch (_error) {
      return false;
    }
  }, []);

  const drainResponseRequests = useCallback(() => {
    if (
      responseActiveRef.current
      || toolExecutionsRef.current > 0
      || pendingResponseRequestsRef.current.size === 0
      || typeof connectionRef.current?.sendEvent !== 'function'
    ) {
      return false;
    }

    const requests = Array.from(pendingResponseRequestsRef.current.entries());
    const responseEvent = requests[0]?.[1] || { type: 'response.create' };
    if (!sendRawEvent(responseEvent)) return false;

    // A default-conversation Response sees every item appended before this
    // request. One response therefore consumes every request currently queued,
    // including audio that arrived while a tool was executing.
    responseActiveRef.current = true;
    requests.forEach(([requestKey]) => {
      completedResponseRequestsRef.current.add(requestKey);
      pendingResponseRequestsRef.current.delete(requestKey);
    });
    while (completedResponseRequestsRef.current.size > MAX_RESPONSE_REQUEST_KEYS) {
      completedResponseRequestsRef.current.delete(
        completedResponseRequestsRef.current.values().next().value,
      );
    }
    return true;
  }, [sendRawEvent]);

  const requestResponse = useCallback((requestKey, responseEvent = { type: 'response.create' }) => {
    if (
      typeof connectionRef.current?.sendEvent !== 'function'
      || !responseEvent
      || responseEvent.type !== 'response.create'
      || responseEvent.response?.conversation === 'none'
    ) {
      return false;
    }

    let normalizedKey = typeof requestKey === 'string'
      ? requestKey.trim().slice(0, 512)
      : '';
    if (!normalizedKey) {
      responseRequestSequenceRef.current += 1;
      normalizedKey = `automatic:${responseRequestSequenceRef.current}`;
    }
    if (
      completedResponseRequestsRef.current.has(normalizedKey)
      || pendingResponseRequestsRef.current.has(normalizedKey)
    ) {
      return true;
    }

    pendingResponseRequestsRef.current.set(normalizedKey, responseEvent);
    drainResponseRequests();
    return true;
  }, [drainResponseRequests]);

  const sendEvent = useCallback((event) => {
    if (
      event?.type === 'response.create'
      && event?.response?.conversation !== 'none'
    ) {
      return requestResponse(event.event_id, event);
    }
    return sendRawEvent(event);
  }, [requestResponse, sendRawEvent]);

  const sendToolOutput = useCallback(
    (callId, output, { createResponse = true } = {}) => {
      if (typeof callId !== 'string' || !callId || callId.length > 256) {
        return false;
      }
      const sent = sendRawEvent({
        type: 'conversation.item.create',
        item: {
          type: 'function_call_output',
          call_id: callId,
          output: serializeToolOutput(output),
        },
      });
      if (!sent) return false;
      return createResponse
        ? requestResponse(`tool-output:${callId}`)
        : true;
    },
    [requestResponse, sendRawEvent],
  );

  const handleToolCallEvent = useCallback(
    (event) => {
      const calls = completedToolCalls(event).filter((call) => {
        if (
          typeof call.callId !== 'string' ||
          !call.callId ||
          call.callId.length > 256 ||
          processedToolCallsRef.current.has(call.callId)
        ) {
          return false;
        }
        processedToolCallsRef.current.add(call.callId);
        if (processedToolCallsRef.current.size > MAX_PROCESSED_TOOL_CALLS) {
          const oldest = processedToolCallsRef.current.values().next().value;
          processedToolCallsRef.current.delete(oldest);
        }
        return true;
      });
      if (!calls.length) return false;

      const connectionAtCall = connectionRef.current;
      const schedulerGenerationAtCall = responseSchedulerGenerationRef.current;
      toolExecutionsRef.current += 1;
      const continuationKey = typeof event?.response?.id === 'string'
        ? `tool-continuation:${event.response.id}`
        : `tool-continuation:${calls.map((call) => call.callId).join(',')}`;
      void Promise.all(calls.map(async (call) => {
          let output;
          try {
            if (
              typeof call.name !== 'string' ||
              !call.name ||
              call.name.length > 128
            ) {
              throw new Error('Invalid tool name.');
            }
            const parsedArguments = parseBoundedToolArguments(call.argumentsJson);
            if (typeof callbacksRef.current.onToolCall !== 'function') {
              output = toolError(
                'tool_unavailable',
                'This game action is not available right now.',
              );
            } else {
              try {
                output = await callbacksRef.current.onToolCall({
                  name: call.name,
                  arguments: parsedArguments,
                  callId: call.callId,
                });
              } catch (_error) {
                output = toolError(
                  'tool_execution_failed',
                  'The game action could not be completed.',
                );
              }
            }
          } catch (_error) {
            output = toolError(
              'invalid_tool_arguments',
              'The game action arguments were invalid.',
            );
          }

          return { callId: call.callId, output };
        })).then((results) => {
          if (
            connectionRef.current !== connectionAtCall
            || !connectionAtCall
            || responseSchedulerGenerationRef.current !== schedulerGenerationAtCall
          ) return;
          const outputsSent = results.map(({ callId, output }) => (
            sendToolOutput(callId, output, { createResponse: false })
          )).every(Boolean);
          toolExecutionsRef.current = Math.max(0, toolExecutionsRef.current - 1);
          if (outputsSent) requestResponse(continuationKey);
          else drainResponseRequests();
        });
      return true;
    },
    [drainResponseRequests, requestResponse, sendToolOutput],
  );

  const handleEvent = useCallback(
    (event) => {
      handleToolCallEvent(event);
      callbacksRef.current.onEvent?.(event);
      const currentTranscript = transcriptRef.current;
      const nextTranscript = reduceTranscriptEvent(currentTranscript, event);
      if (nextTranscript !== currentTranscript) {
        transcriptRef.current = nextTranscript;
        setTranscript(nextTranscript);
        callbacksRef.current.onTranscript?.(nextTranscript, event);
      }

      if (event?.type === 'response.created') {
        responseActiveRef.current = true;
      } else if (event?.type === 'response.done' || event?.type === 'response.cancelled') {
        responseActiveRef.current = false;
        drainResponseRequests();
      }

      if (isAssistantSpeechEvent(event)) {
        setSpeaking(true);
      } else if (isAssistantSpeechDoneEvent(event)) {
        setSpeaking(false);
      } else if (event?.type === 'input_audio_buffer.speech_started') {
        setSpeaking(false);
        transition(VOICE_STATES.LISTENING);
      } else if (event?.type === 'error') {
        failSession(realtimeEventErrorMessage(event));
      }
    },
    [drainResponseRequests, failSession, handleToolCallEvent, setSpeaking, transition],
  );

  const disconnect = useCallback(() => {
    connectAttemptRef.current += 1;
    connectingRef.current = false;
    const connection = connectionRef.current;
    connectionRef.current = null;
    processedToolCallsRef.current.clear();
    resetResponseScheduler();
    connection?.disconnect?.();
    stopAudioMonitor();
    setSpeaking(false);
    stopFallbackPulse();
    if (mountedRef.current) {
      setMutedState(startsMuted);
      transition(VOICE_STATES.IDLE);
    }
  }, [
    resetResponseScheduler,
    setSpeaking,
    startsMuted,
    stopAudioMonitor,
    stopFallbackPulse,
    transition,
  ]);

  const connect = useCallback(async () => {
    if (connectionRef.current || connectingRef.current) return;
    connectingRef.current = true;
    const attempt = connectAttemptRef.current + 1;
    connectAttemptRef.current = attempt;
    let failedDuringConnect = false;
    processedToolCallsRef.current.clear();
    resetResponseScheduler();
    setError(null);
    transition(VOICE_STATES.CONNECTING);

    try {
      const connection = await provider.connect({
        initialMuted: startsMuted,
        onEvent: handleEvent,
        onRemoteStream: handleRemoteStream,
        onConnectionStateChange: (connectionState) => {
          if (connectionState === 'failed') {
            failedDuringConnect = true;
            failSession('The voice connection failed.');
          }
        },
      });
      if (!mountedRef.current || attempt !== connectAttemptRef.current) {
        connection.disconnect?.();
        return;
      }
      if (failedDuringConnect) {
        connectingRef.current = false;
        connection.disconnect?.();
        return;
      }
      connectingRef.current = false;
      connection.setMuted?.(startsMuted);
      connectionRef.current = connection;
      setMutedState(startsMuted);
      transition(
        speakingRef.current ? VOICE_STATES.SPEAKING : VOICE_STATES.LISTENING,
      );
    } catch (connectError) {
      if (!mountedRef.current || attempt !== connectAttemptRef.current) return;
      connectingRef.current = false;
      const nextError = publicError(connectError);
      setError(nextError);
      callbacksRef.current.onError?.(nextError);
      transition(VOICE_STATES.ERROR);
    }
  }, [
    handleEvent,
    handleRemoteStream,
    failSession,
    provider,
    resetResponseScheduler,
    startsMuted,
    transition,
  ]);

  const setMuted = useCallback((nextMuted) => {
    const value = Boolean(nextMuted);
    connectionRef.current?.setMuted?.(value);
    setMutedState(value);
  }, []);

  const toggleMuted = useCallback(() => {
    setMutedState((current) => {
      const next = !current;
      connectionRef.current?.setMuted?.(next);
      return next;
    });
  }, []);

  const clearTranscript = useCallback(() => {
    transcriptRef.current = [];
    setTranscript([]);
  }, []);

  useEffect(() => {
    if (autoConnect) connect();
  }, [autoConnect, connect]);

  useEffect(() => {
    // React 18 development StrictMode performs a setup -> cleanup -> setup
    // rehearsal. Restore the mounted flag on the second setup so a valid
    // Realtime connection is not immediately torn down as if the component
    // were gone for good.
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      connectAttemptRef.current += 1;
      connectingRef.current = false;
      connectionRef.current?.disconnect?.();
      connectionRef.current = null;
      resetResponseScheduler();
      audioMonitorCleanupRef.current?.();
      audioMonitorCleanupRef.current = null;
      if (fallbackPulseRef.current) clearInterval(fallbackPulseRef.current);
    };
  }, [resetResponseScheduler]);

  return {
    provider: provider.id,
    model: provider.defaultModel,
    status,
    isConnected:
      status === VOICE_STATES.LISTENING || status === VOICE_STATES.SPEAKING,
    isSpeaking: status === VOICE_STATES.SPEAKING,
    muted,
    transcript,
    error,
    connect,
    disconnect,
    setMuted,
    toggleMuted,
    clearTranscript,
    sendEvent,
    requestResponse,
    sendToolOutput,
  };
}
