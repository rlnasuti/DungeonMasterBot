import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { VoiceDungeonMaster } from './VoiceDungeonMaster';
import {
  parseBoundedToolArguments,
  startRemoteAudioLevelMonitor,
} from './useVoiceDungeonMaster';

describe('VoiceDungeonMaster', () => {
  test('connects normally after the React StrictMode effect rehearsal', async () => {
    const connection = {
      setMuted: jest.fn(),
      disconnect: jest.fn(),
      sendEvent: jest.fn(),
    };
    const provider = {
      id: 'strict-mode-realtime',
      defaultModel: 'strict-mode-model',
      connect: jest.fn(async () => connection),
    };

    render(
      <React.StrictMode>
        <VoiceDungeonMaster provider={provider}>
          {(voice) => (
            <div>
              <span data-testid="strict-status">{voice.status}</span>
              <button type="button" onClick={voice.connect}>Strict connect</button>
            </div>
          )}
        </VoiceDungeonMaster>
      </React.StrictMode>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Strict connect' }));
    await waitFor(() => {
      expect(screen.getByTestId('strict-status')).toHaveTextContent('listening');
    });
    expect(provider.connect).toHaveBeenCalledTimes(1);
    expect(provider.connect).toHaveBeenCalledWith(
      expect.objectContaining({ initialMuted: true }),
    );
    expect(connection.setMuted).toHaveBeenCalledWith(true);
  });

  test('exposes listening/speaking state, transcripts, mute, and cleanup', async () => {
    let callbacks;
    const connection = {
      setMuted: jest.fn(),
      disconnect: jest.fn(),
    };
    const provider = {
      id: 'mock-realtime',
      defaultModel: 'mock-voice-model',
      connect: jest.fn(async (nextCallbacks) => {
        callbacks = nextCallbacks;
        return connection;
      }),
    };
    const onTranscript = jest.fn();
    const onAudioLevel = jest.fn();

    const { unmount } = render(
      <VoiceDungeonMaster
        provider={provider}
        onTranscript={onTranscript}
        onAudioLevel={onAudioLevel}
      >
        {(voice) => (
          <div>
            <span data-testid="status">{voice.status}</span>
            <span data-testid="transcript">
              {voice.transcript.map((message) => message.text).join('|')}
            </span>
            <button type="button" onClick={voice.connect}>
              Connect
            </button>
            <button type="button" onClick={voice.toggleMuted}>
              Toggle mute
            </button>
            <button type="button" onClick={voice.disconnect}>
              Disconnect
            </button>
          </div>
        )}
      </VoiceDungeonMaster>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Connect' }));
    await waitFor(() => {
      expect(screen.getByTestId('status')).toHaveTextContent('listening');
    });

    act(() => {
      callbacks.onEvent({
        type: 'conversation.item.input_audio_transcription.completed',
        item_id: 'player-1',
        transcript: 'I roll a twelve.',
      });
      callbacks.onEvent({
        type: 'response.output_audio_transcript.delta',
        item_id: 'dm-1',
        delta: 'The lock clicks.',
      });
    });
    expect(screen.getByTestId('status')).toHaveTextContent('speaking');
    expect(screen.getByTestId('transcript')).toHaveTextContent(
      'I roll a twelve.|The lock clicks.',
    );
    expect(onTranscript).toHaveBeenCalled();
    expect(onAudioLevel).toHaveBeenCalledWith(0.34);

    fireEvent.click(screen.getByRole('button', { name: 'Toggle mute' }));
    expect(connection.setMuted).toHaveBeenLastCalledWith(false);

    act(() => callbacks.onEvent({ type: 'response.done' }));
    expect(screen.getByTestId('status')).toHaveTextContent('listening');
    expect(onAudioLevel).toHaveBeenLastCalledWith(0);

    fireEvent.click(screen.getByRole('button', { name: 'Disconnect' }));
    expect(connection.disconnect).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId('status')).toHaveTextContent('idle');

    unmount();
    expect(connection.disconnect).toHaveBeenCalledTimes(1);
  });

  test('meters remote audio at a throttled level between zero and one', () => {
    const originalAudioContext = globalThis.AudioContext;
    const originalRequestAnimationFrame = globalThis.requestAnimationFrame;
    const originalCancelAnimationFrame = globalThis.cancelAnimationFrame;
    const frames = [];
    const analyser = {
      fftSize: 0,
      smoothingTimeConstant: 0,
      getByteTimeDomainData: jest.fn((samples) => samples.fill(160)),
      disconnect: jest.fn(),
    };
    const source = { connect: jest.fn(), disconnect: jest.fn() };
    const close = jest.fn();
    globalThis.AudioContext = class {
      createAnalyser() {
        return analyser;
      }
      createMediaStreamSource() {
        return source;
      }
      close() {
        close();
      }
    };
    globalThis.requestAnimationFrame = jest.fn((callback) => {
      frames.push(callback);
      return frames.length;
    });
    globalThis.cancelAnimationFrame = jest.fn();
    const onAudioLevel = jest.fn();

    try {
      const cleanup = startRemoteAudioLevelMonitor(
        { id: 'remote-stream' },
        onAudioLevel,
      );
      expect(cleanup).toEqual(expect.any(Function));

      frames.shift()(0);
      frames.shift()(20);
      frames.shift()(60);
      expect(onAudioLevel).toHaveBeenCalledTimes(2);
      onAudioLevel.mock.calls.forEach(([level]) => {
        expect(level).toBeGreaterThanOrEqual(0);
        expect(level).toBeLessThanOrEqual(1);
      });

      cleanup();
      expect(source.disconnect).toHaveBeenCalled();
      expect(close).toHaveBeenCalled();
    } finally {
      globalThis.AudioContext = originalAudioContext;
      globalThis.requestAnimationFrame = originalRequestAnimationFrame;
      globalThis.cancelAnimationFrame = originalCancelAnimationFrame;
    }
  });

  test('executes completed tool calls once and returns authoritative output', async () => {
    let callbacks;
    let controls;
    const connection = {
      setMuted: jest.fn(),
      disconnect: jest.fn(),
      sendEvent: jest.fn(),
    };
    const provider = {
      id: 'mock-realtime',
      defaultModel: 'mock-voice-model',
      connect: jest.fn(async (nextCallbacks) => {
        callbacks = nextCallbacks;
        return connection;
      }),
    };
    const onToolCall = jest.fn(async () => ({
      ok: true,
      player: { player_id: 'player-1', hp: 7 },
    }));

    render(
      <VoiceDungeonMaster provider={provider} onToolCall={onToolCall}>
        {(voice) => {
          controls = voice;
          return <button onClick={voice.connect}>Connect tools</button>;
        }}
      </VoiceDungeonMaster>,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Connect tools' }));
    await waitFor(() => expect(controls.status).toBe('listening'));

    act(() => {
      callbacks.onEvent({
        type: 'response.function_call_arguments.done',
        name: 'apply_damage',
        call_id: 'call-damage-1',
        arguments: '{"player_id":"player-1","amount":3}',
      });
    });
    expect(onToolCall).not.toHaveBeenCalled();
    expect(connection.sendEvent).not.toHaveBeenCalled();

    act(() => {
      callbacks.onEvent({
        type: 'response.done',
        response: {
          output: [
            {
              type: 'function_call',
              status: 'completed',
              name: 'apply_damage',
              call_id: 'call-damage-1',
              arguments: '{"player_id":"player-1","amount":3}',
            },
          ],
        },
      });
    });
    await waitFor(() => {
      expect(onToolCall).toHaveBeenCalledWith({
        name: 'apply_damage',
        arguments: { player_id: 'player-1', amount: 3 },
        callId: 'call-damage-1',
      });
      expect(connection.sendEvent).toHaveBeenCalledTimes(2);
    });
    expect(connection.sendEvent).toHaveBeenNthCalledWith(1, {
      type: 'conversation.item.create',
      item: {
        type: 'function_call_output',
        call_id: 'call-damage-1',
        output: JSON.stringify({
          ok: true,
          player: { player_id: 'player-1', hp: 7 },
        }),
      },
    });
    expect(connection.sendEvent).toHaveBeenNthCalledWith(2, {
      type: 'response.create',
    });

    act(() => callbacks.onEvent({
      type: 'response.function_call_arguments.done',
      name: 'apply_damage',
      call_id: 'call-damage-1',
      arguments: '{"player_id":"player-1","amount":3}',
    }));
    expect(onToolCall).toHaveBeenCalledTimes(1);

    expect(controls.sendEvent({ type: 'response.cancel' })).toBe(true);
    expect(controls.sendToolOutput('manual-call', { ok: true })).toBe(true);
    expect(connection.sendEvent).toHaveBeenLastCalledWith(expect.objectContaining({
      type: 'conversation.item.create',
      item: expect.objectContaining({ call_id: 'manual-call' }),
    }));
    act(() => callbacks.onEvent({
      type: 'response.done',
      response: { status: 'completed', output: [] },
    }));
    expect(connection.sendEvent).toHaveBeenLastCalledWith({
      type: 'response.create',
    });
  });

  test('serializes and coalesces concurrent default-conversation response requests', async () => {
    let callbacks;
    let controls;
    const connection = {
      disconnect: jest.fn(),
      sendEvent: jest.fn(),
    };
    const provider = {
      id: 'mock-realtime',
      defaultModel: 'mock-voice-model',
      connect: jest.fn(async (nextCallbacks) => {
        callbacks = nextCallbacks;
        return connection;
      }),
    };

    render(
      <VoiceDungeonMaster provider={provider}>
        {(voice) => {
          controls = voice;
          return <button onClick={voice.connect}>Connect scheduler</button>;
        }}
      </VoiceDungeonMaster>,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Connect scheduler' }));
    await waitFor(() => expect(controls.status).toBe('listening'));

    expect(controls.requestResponse('opening')).toBe(true);
    expect(controls.requestResponse('typed:turn-1')).toBe(true);
    expect(controls.requestResponse('audio:turn-2')).toBe(true);
    expect(controls.requestResponse('audio:turn-2')).toBe(true);
    expect(connection.sendEvent.mock.calls.filter(
      ([event]) => event.type === 'response.create',
    )).toHaveLength(1);

    act(() => callbacks.onEvent({
      type: 'response.done',
      response: { id: 'opening-response', status: 'completed', output: [] },
    }));
    expect(connection.sendEvent.mock.calls.filter(
      ([event]) => event.type === 'response.create',
    )).toHaveLength(2);

    act(() => callbacks.onEvent({
      type: 'response.done',
      response: { id: 'combined-response', status: 'completed', output: [] },
    }));
    expect(connection.sendEvent.mock.calls.filter(
      ([event]) => event.type === 'response.create',
    )).toHaveLength(2);
  });

  test('coalesces audio and typed turns into the pending tool continuation exactly once', async () => {
    let callbacks;
    let controls;
    let resolveTool;
    const connection = {
      disconnect: jest.fn(),
      sendEvent: jest.fn(),
    };
    const provider = {
      id: 'mock-realtime',
      defaultModel: 'mock-voice-model',
      connect: jest.fn(async (nextCallbacks) => {
        callbacks = nextCallbacks;
        return connection;
      }),
    };
    const onToolCall = jest.fn(() => new Promise((resolve) => {
      resolveTool = resolve;
    }));

    render(
      <VoiceDungeonMaster provider={provider} onToolCall={onToolCall}>
        {(voice) => {
          controls = voice;
          return <button onClick={voice.connect}>Connect tool scheduler</button>;
        }}
      </VoiceDungeonMaster>,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Connect tool scheduler' }));
    await waitFor(() => expect(controls.status).toBe('listening'));
    controls.requestResponse('opening');

    act(() => callbacks.onEvent({
      type: 'response.done',
      response: {
        id: 'response-with-tool',
        status: 'completed',
        output: [{
          type: 'function_call',
          status: 'completed',
          name: 'read_public_game_state',
          call_id: 'call-state-1',
          arguments: '{}',
        }],
      },
    }));
    expect(onToolCall).toHaveBeenCalledTimes(1);
    controls.requestResponse('audio:turn-during-tool');
    controls.requestResponse('typed:turn-during-tool');
    expect(connection.sendEvent.mock.calls.filter(
      ([event]) => event.type === 'response.create',
    )).toHaveLength(1);

    await act(async () => {
      resolveTool({ ok: true, state_version: 12 });
      await Promise.resolve();
    });
    await waitFor(() => expect(connection.sendEvent.mock.calls.filter(
      ([event]) => event.type === 'response.create',
    )).toHaveLength(2));

    act(() => callbacks.onEvent({
      type: 'response.done',
      response: { id: 'tool-continuation', status: 'completed', output: [] },
    }));
    expect(connection.sendEvent.mock.calls.filter(
      ([event]) => event.type === 'response.create',
    )).toHaveLength(2);
  });

  test('does not wedge queued turns when a malformed tool call is dropped', async () => {
    let callbacks;
    let controls;
    const connection = {
      disconnect: jest.fn(),
      sendEvent: jest.fn(),
    };
    const provider = {
      id: 'mock-realtime',
      defaultModel: 'mock-voice-model',
      connect: jest.fn(async (nextCallbacks) => {
        callbacks = nextCallbacks;
        return connection;
      }),
    };
    const onToolCall = jest.fn();

    render(
      <VoiceDungeonMaster provider={provider} onToolCall={onToolCall}>
        {(voice) => {
          controls = voice;
          return <button onClick={voice.connect}>Connect malformed tool</button>;
        }}
      </VoiceDungeonMaster>,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Connect malformed tool' }));
    await waitFor(() => expect(controls.status).toBe('listening'));
    controls.requestResponse('opening');
    controls.requestResponse('audio:waiting-turn');

    act(() => callbacks.onEvent({
      type: 'response.done',
      response: {
        id: 'malformed-tool-response',
        status: 'completed',
        output: [{
          type: 'function_call',
          status: 'completed',
          name: 'read_public_game_state',
          arguments: '{}',
        }],
      },
    }));
    expect(onToolCall).not.toHaveBeenCalled();
    expect(connection.sendEvent.mock.calls.filter(
      ([event]) => event.type === 'response.create',
    )).toHaveLength(2);
  });

  test('clears pending and completed response keys across reconnects', async () => {
    let callbacks;
    let controls;
    const connection = {
      disconnect: jest.fn(),
      sendEvent: jest.fn(),
    };
    const provider = {
      id: 'mock-realtime',
      defaultModel: 'mock-voice-model',
      connect: jest.fn(async (nextCallbacks) => {
        callbacks = nextCallbacks;
        return connection;
      }),
    };

    render(
      <VoiceDungeonMaster provider={provider}>
        {(voice) => {
          controls = voice;
          return (
            <div>
              <button onClick={voice.connect}>Connect reset scheduler</button>
              <button onClick={voice.disconnect}>Disconnect reset scheduler</button>
            </div>
          );
        }}
      </VoiceDungeonMaster>,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Connect reset scheduler' }));
    await waitFor(() => expect(controls.status).toBe('listening'));
    controls.requestResponse('opening');
    controls.requestResponse('audio:stale-turn');

    fireEvent.click(screen.getByRole('button', { name: 'Disconnect reset scheduler' }));
    fireEvent.click(screen.getByRole('button', { name: 'Connect reset scheduler' }));
    await waitFor(() => expect(provider.connect).toHaveBeenCalledTimes(2));
    expect(controls.requestResponse('opening')).toBe(true);
    expect(connection.sendEvent.mock.calls.filter(
      ([event]) => event.type === 'response.create',
    )).toHaveLength(2);

    act(() => callbacks.onEvent({
      type: 'response.done',
      response: { id: 'new-opening', status: 'completed', output: [] },
    }));
    expect(connection.sendEvent.mock.calls.filter(
      ([event]) => event.type === 'response.create',
    )).toHaveLength(2);
  });

  test('returns sanitized tool errors for malformed arguments and executor failures', async () => {
    let callbacks;
    let controls;
    const connection = {
      disconnect: jest.fn(),
      sendEvent: jest.fn(),
    };
    const provider = {
      id: 'mock-realtime',
      defaultModel: 'mock-voice-model',
      connect: jest.fn(async (nextCallbacks) => {
        callbacks = nextCallbacks;
        return connection;
      }),
    };
    const onToolCall = jest.fn(async () => {
      throw new Error('sensitive database diagnostic');
    });

    render(
      <VoiceDungeonMaster provider={provider} onToolCall={onToolCall}>
        {(voice) => {
          controls = voice;
          return <button onClick={voice.connect}>Connect errors</button>;
        }}
      </VoiceDungeonMaster>,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Connect errors' }));
    await waitFor(() => expect(controls.status).toBe('listening'));

    act(() => {
      callbacks.onEvent({
        type: 'response.done',
        response: {
          output: [
            {
              type: 'function_call',
              status: 'completed',
              name: 'apply_healing',
              call_id: 'call-invalid',
              arguments: '{"amount":',
            },
            {
              type: 'function_call',
              status: 'completed',
              name: 'apply_healing',
              call_id: 'call-failed',
              arguments: '{"player_id":"player-1","amount":2}',
            },
          ],
        },
      });
    });

    await waitFor(() => expect(connection.sendEvent).toHaveBeenCalledTimes(3));
    const outputs = connection.sendEvent.mock.calls
      .map(([event]) => event.item?.output)
      .filter(Boolean)
      .map(JSON.parse);
    expect(outputs).toEqual([
      expect.objectContaining({
        error: expect.objectContaining({ code: 'invalid_tool_arguments' }),
      }),
      expect.objectContaining({
        error: expect.objectContaining({ code: 'tool_execution_failed' }),
      }),
    ]);
    expect(JSON.stringify(outputs)).not.toContain('sensitive database diagnostic');
    expect(onToolCall).toHaveBeenCalledTimes(1);
    expect(connection.sendEvent.mock.calls.filter(
      ([event]) => event.type === 'response.create',
    )).toHaveLength(1);
  });

  test('bounds and hardens parsed tool arguments', () => {
    expect(parseBoundedToolArguments('{"amount":2}')).toEqual({ amount: 2 });
    expect(() => parseBoundedToolArguments('[]')).toThrow('Invalid tool arguments.');
    expect(() =>
      parseBoundedToolArguments(`{"value":"${'x'.repeat(33_000)}"}`),
    ).toThrow('Invalid tool arguments.');
    expect(() =>
      parseBoundedToolArguments('{"__proto__":{"polluted":true}}'),
    ).toThrow('Invalid tool arguments.');
  });
});
