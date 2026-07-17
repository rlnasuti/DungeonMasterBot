/* global globalThis */

export const OPENAI_REALTIME_PROVIDER_ID = 'openai-realtime';
export const GPT_LIVE_PROVIDER_ID = 'gpt-live';
export const DEFAULT_REALTIME_MODEL = 'gpt-realtime-2.1';

const DEFAULT_CLIENT_SECRET_URL =
  process.env.REACT_APP_REALTIME_CLIENT_SECRET_URL ||
  'http://localhost:8000/api/realtime/client-secret';
const DEFAULT_REALTIME_CALLS_URL = 'https://api.openai.com/v1/realtime/calls';
const DATA_CHANNEL_OPEN_TIMEOUT_MS = 10_000;

export class RealtimeConnectionError extends Error {
  constructor(code, message) {
    super(message);
    this.name = 'RealtimeConnectionError';
    this.code = code;
  }
}

function safeConnectionError(code, message) {
  return new RealtimeConnectionError(code, message);
}

function requireBrowserDependency(value, name) {
  if (!value) {
    throw safeConnectionError(
      'browser_not_supported',
      `Voice chat requires browser support for ${name}.`,
    );
  }
  return value;
}

function waitForDataChannelOpen(channel, timeoutMs = DATA_CHANNEL_OPEN_TIMEOUT_MS) {
  if (channel.readyState === 'open') {
    return Promise.resolve();
  }

  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      cleanup();
      reject(
        safeConnectionError(
          'connection_timeout',
          'The voice connection took too long to open.',
        ),
      );
    }, timeoutMs);

    const cleanup = () => {
      clearTimeout(timeout);
      channel.removeEventListener?.('open', handleOpen);
      channel.removeEventListener?.('close', handleClose);
      channel.removeEventListener?.('error', handleError);
    };
    const handleOpen = () => {
      cleanup();
      resolve();
    };
    const handleClose = () => {
      cleanup();
      reject(
        safeConnectionError(
          'connection_closed',
          'The voice connection closed before it was ready.',
        ),
      );
    };
    const handleError = () => {
      cleanup();
      reject(
        safeConnectionError(
          'connection_failed',
          'The browser could not open the voice connection.',
        ),
      );
    };

    channel.addEventListener?.('open', handleOpen);
    channel.addEventListener?.('close', handleClose);
    channel.addEventListener?.('error', handleError);
  });
}

function parseServerEvent(rawEvent) {
  try {
    const event = JSON.parse(rawEvent);
    return event && typeof event === 'object' ? event : null;
  } catch (_error) {
    return null;
  }
}

function stopStream(stream) {
  stream?.getTracks?.().forEach((track) => track.stop());
}

/**
 * Create the OpenAI implementation of the browser voice-provider boundary.
 * A future GPT-Live adapter can expose the same { id, defaultModel, connect }
 * contract without changing the VoiceDungeonMaster hook or component.
 */
export function createOpenAIRealtimeProvider(options = {}) {
  const {
    clientSecretUrl = DEFAULT_CLIENT_SECRET_URL,
    realtimeCallsUrl = DEFAULT_REALTIME_CALLS_URL,
    fetchImpl = globalThis.fetch?.bind(globalThis),
    RTCPeerConnectionImpl = globalThis.RTCPeerConnection,
    getUserMedia = globalThis.navigator?.mediaDevices?.getUserMedia?.bind(
      globalThis.navigator.mediaDevices,
    ),
    createAudioElement = () => globalThis.document?.createElement('audio'),
    dataChannelOpenTimeoutMs = DATA_CHANNEL_OPEN_TIMEOUT_MS,
  } = options;

  return {
    id: OPENAI_REALTIME_PROVIDER_ID,
    defaultModel: DEFAULT_REALTIME_MODEL,

    async connect(callbacks = {}) {
      const {
        onEvent = () => {},
        onRemoteStream = () => {},
        onConnectionStateChange = () => {},
        initialMuted = false,
      } = callbacks;

      const request = requireBrowserDependency(fetchImpl, 'network requests');
      const PeerConnection = requireBrowserDependency(
        RTCPeerConnectionImpl,
        'WebRTC',
      );
      const requestMicrophone = requireBrowserDependency(
        getUserMedia,
        'microphone access',
      );

      let localStream;
      let peerConnection;
      let dataChannel;
      let audioElement;
      let disconnected = false;

      const disconnect = () => {
        if (disconnected) return;
        disconnected = true;
        if (dataChannel) {
          dataChannel.onmessage = null;
          dataChannel.close?.();
        }
        if (peerConnection) {
          peerConnection.ontrack = null;
          peerConnection.onconnectionstatechange = null;
          peerConnection.close?.();
        }
        stopStream(localStream);
        if (audioElement) {
          audioElement.pause?.();
          audioElement.srcObject = null;
          audioElement.remove?.();
        }
      };

      try {
        const tokenResponse = await request(clientSecretUrl, {
          method: 'POST',
          headers: { Accept: 'application/json' },
          cache: 'no-store',
        });
        if (!tokenResponse.ok) {
          throw safeConnectionError(
            'credential_unavailable',
            'Voice service credentials are temporarily unavailable.',
          );
        }

        const tokenPayload = await tokenResponse.json();
        const clientSecret = tokenPayload?.client_secret;
        if (typeof clientSecret !== 'string' || !clientSecret) {
          throw safeConnectionError(
            'credential_invalid',
            'Voice service returned an invalid short-lived credential.',
          );
        }

        peerConnection = new PeerConnection();
        audioElement = createAudioElement?.();
        if (audioElement) {
          audioElement.autoplay = true;
          audioElement.playsInline = true;
        }

        peerConnection.ontrack = (event) => {
          const remoteStream = event.streams?.[0];
          if (!remoteStream) return;
          if (audioElement) {
            audioElement.srcObject = remoteStream;
            const playResult = audioElement.play?.();
            playResult?.catch?.(() => {
              // Some browsers require a second user gesture to begin playback.
              // The stream is still exposed for UI-level recovery and metering.
            });
          }
          onRemoteStream(remoteStream);
        };

        peerConnection.onconnectionstatechange = () => {
          onConnectionStateChange(peerConnection.connectionState);
        };

        localStream = await requestMicrophone({
          audio: {
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
          },
        });
        localStream.getAudioTracks().forEach((track) => {
          // Apply the privacy state before the track is attached to WebRTC so
          // no captured audio can leak through while React finishes rendering
          // the connected controls.
          track.enabled = !Boolean(initialMuted);
          peerConnection.addTrack(track, localStream);
        });

        dataChannel = peerConnection.createDataChannel('oai-events');
        dataChannel.onmessage = (message) => {
          const event = parseServerEvent(message.data);
          if (event) onEvent(event);
        };

        const offer = await peerConnection.createOffer();
        await peerConnection.setLocalDescription(offer);

        const answerResponse = await request(realtimeCallsUrl, {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${clientSecret}`,
            'Content-Type': 'application/sdp',
          },
          body: peerConnection.localDescription?.sdp || offer.sdp,
        });
        if (!answerResponse.ok) {
          throw safeConnectionError(
            'session_unavailable',
            'The realtime voice session could not be created.',
          );
        }

        const answerSdp = await answerResponse.text();
        await peerConnection.setRemoteDescription({
          type: 'answer',
          sdp: answerSdp,
        });
        await waitForDataChannelOpen(dataChannel, dataChannelOpenTimeoutMs);

        return {
          provider: tokenPayload.provider || OPENAI_REALTIME_PROVIDER_ID,
          model: tokenPayload.model || DEFAULT_REALTIME_MODEL,
          setMuted(muted) {
            localStream?.getAudioTracks?.().forEach((track) => {
              track.enabled = !muted;
            });
          },
          sendEvent(event) {
            if (dataChannel?.readyState !== 'open') {
              throw safeConnectionError(
                'connection_not_ready',
                'The voice connection is not ready.',
              );
            }
            dataChannel.send(JSON.stringify(event));
          },
          disconnect,
        };
      } catch (error) {
        disconnect();
        if (error instanceof RealtimeConnectionError) throw error;
        if (error?.name === 'NotAllowedError') {
          throw safeConnectionError(
            'microphone_denied',
            'Microphone permission is required for voice chat.',
          );
        }
        throw safeConnectionError(
          'connection_failed',
          'The browser could not start the voice connection.',
        );
      }
    },
  };
}

export const openAIRealtimeProvider = createOpenAIRealtimeProvider();
