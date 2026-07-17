import {
  RealtimeConnectionError,
  createOpenAIRealtimeProvider,
} from './realtimeProvider';

class FakeDataChannel {
  constructor() {
    this.readyState = 'open';
    this.listeners = {};
    this.close = jest.fn(() => {
      this.readyState = 'closed';
    });
    this.send = jest.fn();
  }

  addEventListener(type, listener) {
    this.listeners[type] = listener;
  }

  removeEventListener(type) {
    delete this.listeners[type];
  }
}

class FakePeerConnection {
  static instance = null;

  constructor() {
    FakePeerConnection.instance = this;
    this.channel = new FakeDataChannel();
    this.connectionState = 'connected';
    this.addTrack = jest.fn((track) => {
      this.trackEnabledWhenAttached = track.enabled;
    });
    this.close = jest.fn();
    this.createOffer = jest.fn(async () => ({
      type: 'offer',
      sdp: 'browser-offer-sdp',
    }));
    this.setLocalDescription = jest.fn(async (offer) => {
      this.localDescription = offer;
    });
    this.setRemoteDescription = jest.fn(async () => {});
  }

  createDataChannel() {
    return this.channel;
  }
}

function jsonResponse(payload, ok = true) {
  return {
    ok,
    json: jest.fn(async () => payload),
  };
}

function sdpResponse(sdp, ok = true) {
  return {
    ok,
    text: jest.fn(async () => sdp),
  };
}

describe('OpenAI Realtime WebRTC provider', () => {
  test('uses the ephemeral secret for SDP exchange and cleans up media', async () => {
    const microphoneTrack = { enabled: true, stop: jest.fn() };
    const localStream = {
      getAudioTracks: () => [microphoneTrack],
      getTracks: () => [microphoneTrack],
    };
    const remoteStream = { id: 'remote-audio' };
    const audioElement = {
      play: jest.fn(async () => {}),
      pause: jest.fn(),
      remove: jest.fn(),
      srcObject: null,
    };
    const fetchImpl = jest
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          provider: 'openai-realtime',
          model: 'gpt-realtime-2.1',
          client_secret: 'short-lived-client-secret',
        }),
      )
      .mockResolvedValueOnce(sdpResponse('openai-answer-sdp'));
    const onRemoteStream = jest.fn();
    const onEvent = jest.fn();
    const provider = createOpenAIRealtimeProvider({
      clientSecretUrl: '/test-client-secret',
      realtimeCallsUrl: 'https://api.openai.test/realtime/calls',
      fetchImpl,
      RTCPeerConnectionImpl: FakePeerConnection,
      getUserMedia: jest.fn(async () => localStream),
      createAudioElement: () => audioElement,
    });

    const connection = await provider.connect({
      onRemoteStream,
      onEvent,
      initialMuted: true,
    });
    const peer = FakePeerConnection.instance;
    peer.ontrack({ streams: [remoteStream] });
    peer.channel.onmessage({
      data: JSON.stringify({ type: 'response.done', response: { id: 'r1' } }),
    });

    expect(fetchImpl).toHaveBeenNthCalledWith(
      1,
      '/test-client-secret',
      expect.objectContaining({ method: 'POST', cache: 'no-store' }),
    );
    expect(fetchImpl.mock.calls[0][1].headers.Authorization).toBeUndefined();
    expect(fetchImpl).toHaveBeenNthCalledWith(
      2,
      'https://api.openai.test/realtime/calls',
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: 'Bearer short-lived-client-secret',
          'Content-Type': 'application/sdp',
        }),
        body: 'browser-offer-sdp',
      }),
    );
    expect(peer.setRemoteDescription).toHaveBeenCalledWith({
      type: 'answer',
      sdp: 'openai-answer-sdp',
    });
    expect(audioElement.srcObject).toBe(remoteStream);
    expect(onRemoteStream).toHaveBeenCalledWith(remoteStream);
    expect(onEvent).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'response.done' }),
    );
    expect(peer.trackEnabledWhenAttached).toBe(false);
    expect(microphoneTrack.enabled).toBe(false);

    connection.setMuted(false);
    expect(microphoneTrack.enabled).toBe(true);
    connection.setMuted(true);
    expect(microphoneTrack.enabled).toBe(false);
    connection.sendEvent({ type: 'response.cancel' });
    expect(peer.channel.send).toHaveBeenCalledWith(
      JSON.stringify({ type: 'response.cancel' }),
    );
    connection.disconnect();
    expect(microphoneTrack.stop).toHaveBeenCalled();
    expect(peer.close).toHaveBeenCalled();
    expect(audioElement.pause).toHaveBeenCalled();
  });

  test('sanitizes credential failures without attempting WebRTC', async () => {
    const fetchImpl = jest.fn().mockResolvedValue(jsonResponse({}, false));
    const provider = createOpenAIRealtimeProvider({
      fetchImpl,
      RTCPeerConnectionImpl: FakePeerConnection,
      getUserMedia: jest.fn(),
    });

    await expect(provider.connect()).rejects.toEqual(
      expect.objectContaining({
        name: 'RealtimeConnectionError',
        code: 'credential_unavailable',
      }),
    );
    await expect(provider.connect()).rejects.toBeInstanceOf(
      RealtimeConnectionError,
    );
  });
});
