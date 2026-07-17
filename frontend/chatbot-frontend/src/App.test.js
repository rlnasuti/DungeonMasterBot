import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import App, { ACTIVE_SESSION_STORAGE_KEY } from './App';
import { SESSION_RESUME_PREFIX } from './conversation/resumeContext';

const mockConnect = jest.fn();
const mockDisconnect = jest.fn();
const mockToggleMuted = jest.fn();
const mockSetMuted = jest.fn();
const mockClearTranscript = jest.fn();
const mockSendEvent = jest.fn(() => true);
const mockRequestResponse = jest.fn(() => true);
let mockVoiceOptions;
const mockVoice = {
  status: 'idle',
  isConnected: false,
  muted: true,
  model: 'test-realtime',
  error: null,
  connect: mockConnect,
  disconnect: mockDisconnect,
  toggleMuted: mockToggleMuted,
  setMuted: mockSetMuted,
  clearTranscript: mockClearTranscript,
  sendEvent: mockSendEvent,
  requestResponse: mockRequestResponse,
};

jest.mock('./character', () => ({
  CharacterPanel: () => <div aria-label="Character sheets">Live character sheets</div>,
  CharacterSetup: ({ onComplete }) => (
    <section aria-label="Character setup">
      <p>Guided character setup</p>
      <button
        type="button"
        onClick={() => onComplete({ session_id: 'guided-one-shot-v2' })}
      >
        Confirm test characters
      </button>
    </section>
  ),
}));

jest.mock('./voice', () => ({
  VOICE_STATES: {
    IDLE: 'idle',
    CONNECTING: 'connecting',
    LISTENING: 'listening',
    SPEAKING: 'speaking',
    ERROR: 'error',
  },
  VoiceDungeonMaster: (props) => {
    mockVoiceOptions = props;
    return props.children(mockVoice);
  },
}));

function jsonResponse(payload, { ok = true, status = 200 } = {}) {
  return {
    ok,
    status,
    json: async () => payload,
  };
}

const emptyPartySnapshot = {
  session_id: 'guided-one-shot-v2',
  state_version: 0,
  players: [
    { player_id: 'player-one', display_name: 'Player One', character_status: 'empty' },
    { player_id: 'player-two', display_name: 'Player Two', character_status: 'empty' },
  ],
};

const confirmedPartySnapshot = {
  ...emptyPartySnapshot,
  session_id: 'one-shot-speakers',
  state_version: 8,
  players: [
    {
      player_id: 'player-one',
      display_name: 'Robert',
      character_status: 'confirmed',
      character: { name: 'Cendien' },
    },
    {
      player_id: 'player-two',
      display_name: 'Juice',
      character_status: 'confirmed',
      character: { name: 'Juicebox' },
    },
  ],
};

function useConfirmedSpeakerSession() {
  window.localStorage.setItem(ACTIVE_SESSION_STORAGE_KEY, confirmedPartySnapshot.session_id);
  global.fetch = jest.fn(async (url, options = {}) => {
    if (String(url).endsWith(`/api/sessions/${confirmedPartySnapshot.session_id}/view`)) {
      return jsonResponse(confirmedPartySnapshot);
    }
    if (String(url).endsWith(`/api/sessions/${confirmedPartySnapshot.session_id}/conversation`)) {
      if (options.method === 'DELETE') return jsonResponse({ ok: true });
      return jsonResponse({ session_id: confirmedPartySnapshot.session_id, messages: [] });
    }
    if (String(url).includes('/conversation/messages/') && options.method === 'PUT') {
      return jsonResponse({ ok: true });
    }
    throw new Error(`Unexpected test request: ${url}`);
  });
}

beforeEach(() => {
  jest.clearAllMocks();
  window.localStorage.clear();
  mockVoiceOptions = null;
  mockSendEvent.mockReturnValue(true);
  mockRequestResponse.mockReturnValue(true);
  Object.assign(mockVoice, {
    status: 'idle',
    isConnected: false,
    muted: true,
    error: null,
  });
  global.fetch = jest.fn(async (url, options = {}) => {
    if (String(url).endsWith('/api/sessions/latest')) {
      return jsonResponse(
        { error: { message: 'No sessions exist.' } },
        { ok: false, status: 404 },
      );
    }
    if (String(url).endsWith('/api/sessions') && options.method === 'POST') {
      return jsonResponse(emptyPartySnapshot, { status: 201 });
    }
    if (String(url).includes('/api/sessions/guided-one-shot-v2/view')) {
      return jsonResponse(emptyPartySnapshot);
    }
    if (String(url).endsWith('/api/sessions/guided-one-shot-v2/conversation')) {
      if (options.method === 'DELETE') return jsonResponse({ ok: true });
      return jsonResponse({ session_id: 'guided-one-shot-v2', messages: [] });
    }
    if (String(url).includes('/conversation/messages/') && options.method === 'PUT') {
      return jsonResponse({ ok: true });
    }
    throw new Error(`Unexpected test request: ${url}`);
  });
});

afterEach(() => {
  jest.restoreAllMocks();
});

test('prepares a blank guided party instead of bootstrapping demo characters', async () => {
  render(<App />);

  expect(screen.getByRole('heading', { name: /bell beneath briar glen/i })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /begin voice adventure/i })).toBeDisabled();
  expect(screen.getByLabelText(/message input/i)).toBeDisabled();

  await waitFor(() => {
    expect(screen.getByRole('button', { name: /begin voice adventure/i })).toBeEnabled();
  });
  expect(screen.getByText(/your adventurers await/i)).toBeInTheDocument();
  expect(screen.queryByText('Live character sheets')).not.toBeInTheDocument();

  const postCall = global.fetch.mock.calls.find(([, options]) => options?.method === 'POST');
  expect(postCall).toBeDefined();
  expect(JSON.parse(postCall[1].body)).toMatchObject({
    session_id: 'guided-one-shot-v2',
    players: [
      { player_id: 'player-one' },
      { player_id: 'player-two' },
    ],
  });
  expect(global.fetch.mock.calls.some(([url]) => String(url).includes('/api/demo-sessions'))).toBe(false);
  expect(global.fetch.mock.calls.some(([url]) => String(url).endsWith('/guided-one-shot-v2/view'))).toBe(true);
});

test('collapses and reopens the live party state without unmounting the workspace', async () => {
  render(<App />);
  await waitFor(() => {
    expect(screen.getByRole('button', { name: /begin voice adventure/i })).toBeEnabled();
  });

  const layout = document.querySelector('.layout');
  const partyContent = document.getElementById('party-state-content');
  const hideButton = screen.getByRole('button', { name: /hide live party state/i });
  expect(layout).not.toHaveClass('layout--party-collapsed');
  expect(hideButton).toHaveAttribute('aria-expanded', 'true');
  expect(partyContent).not.toHaveAttribute('hidden');

  fireEvent.click(hideButton);

  const showButton = screen.getByRole('button', { name: /show live party state/i });
  expect(layout).toHaveClass('layout--party-collapsed');
  expect(showButton).toHaveAttribute('aria-expanded', 'false');
  expect(showButton).toHaveAttribute('aria-controls', 'party-state-content');
  expect(partyContent).toHaveAttribute('hidden');

  fireEvent.click(showButton);

  expect(layout).not.toHaveClass('layout--party-collapsed');
  expect(screen.getByRole('button', { name: /hide live party state/i }))
    .toHaveAttribute('aria-expanded', 'true');
  expect(partyContent).not.toHaveAttribute('hidden');
  expect(screen.getByLabelText(/message input/i)).toBeInTheDocument();
});

test('starts muted and switches one character microphone at a time', async () => {
  useConfirmedSpeakerSession();
  Object.assign(mockVoice, { status: 'listening', isConnected: true, muted: true });
  render(<App />);

  const cendienButton = await screen.findByRole('button', { name: 'Cendien microphone' });
  const juiceboxButton = screen.getByRole('button', { name: 'Juicebox microphone' });
  expect(cendienButton).toHaveAttribute('aria-pressed', 'false');
  expect(juiceboxButton).toHaveAttribute('aria-pressed', 'false');
  expect(screen.getByText(/microphone muted\. choose a character/i)).toBeInTheDocument();

  mockSendEvent.mockClear();
  mockSetMuted.mockClear();
  fireEvent.click(cendienButton);

  expect(mockSetMuted).toHaveBeenNthCalledWith(1, true);
  expect(mockSetMuted).toHaveBeenNthCalledWith(2, false);
  expect(mockSendEvent).toHaveBeenCalledWith(expect.objectContaining({
    type: 'conversation.item.create',
    item: expect.objectContaining({ role: 'system' }),
  }));
  const selectionEvent = mockSendEvent.mock.calls[0][0];
  expect(selectionEvent.item.content[0].text).toContain('APP-OWNED SPEAKER SELECTION');
  expect(selectionEvent.item.content[0].text).toContain('"character_name":"Cendien"');
  expect(mockSendEvent.mock.invocationCallOrder[0])
    .toBeLessThan(mockSetMuted.mock.invocationCallOrder[1]);
  expect(cendienButton).toHaveAttribute('aria-pressed', 'true');
  expect(juiceboxButton).toHaveAttribute('aria-pressed', 'false');

  fireEvent.click(juiceboxButton);
  expect(cendienButton).toHaveAttribute('aria-pressed', 'false');
  expect(juiceboxButton).toHaveAttribute('aria-pressed', 'true');
  expect(screen.getByText(/juicebox microphone is live/i)).toBeInTheDocument();

  fireEvent.click(juiceboxButton);
  expect(cendienButton).toHaveAttribute('aria-pressed', 'false');
  expect(juiceboxButton).toHaveAttribute('aria-pressed', 'false');
  expect(mockSetMuted).toHaveBeenLastCalledWith(true);
  expect(screen.getByText(/microphone muted\. choose a character/i)).toBeInTheDocument();
});

test('anchors each committed audio item to the selected character and labels its transcript', async () => {
  useConfirmedSpeakerSession();
  Object.assign(mockVoice, { status: 'listening', isConnected: true, muted: true });
  render(<App />);

  fireEvent.click(await screen.findByRole('button', { name: 'Cendien microphone' }));
  mockSendEvent.mockClear();
  mockRequestResponse.mockClear();

  act(() => {
    mockVoiceOptions.onEvent({
      type: 'input_audio_buffer.speech_started',
      item_id: 'audio-turn-1',
    });
    mockVoiceOptions.onEvent({
      type: 'conversation.item.created',
      item: {
        id: 'audio-turn-1',
        type: 'message',
        role: 'user',
        content: [{ type: 'input_text', text: 'not the committed audio item' }],
      },
    });
  });
  expect(mockSendEvent).not.toHaveBeenCalled();

  act(() => {
    mockVoiceOptions.onEvent({
      type: 'conversation.item.added',
      item: {
        id: 'audio-turn-1',
        type: 'message',
        role: 'user',
        content: [{ type: 'input_audio', audio: null }],
      },
    });
  });

  expect(mockSendEvent).toHaveBeenNthCalledWith(1, expect.objectContaining({
    type: 'conversation.item.create',
    previous_item_id: 'audio-turn-1',
    item: expect.objectContaining({ role: 'system' }),
  }));
  expect(mockSendEvent.mock.calls[0][0].item.content[0].text)
    .toContain('"character_name":"Cendien"');
  expect(mockRequestResponse).toHaveBeenCalledWith('audio:audio-turn-1');

  act(() => {
    mockVoiceOptions.onEvent({
      type: 'conversation.item.created',
      item: {
        id: 'audio-turn-1',
        type: 'message',
        role: 'user',
        content: [{ type: 'input_audio', audio: null }],
      },
    });
  });
  expect(mockSendEvent).toHaveBeenCalledTimes(1);
  expect(mockRequestResponse).toHaveBeenCalledTimes(1);

  act(() => {
    mockVoiceOptions.onTranscript([{
      id: 'user:audio-turn-1',
      role: 'user',
      text: 'I inspect the stairwell.',
      final: true,
    }]);
  });
  expect(screen.getByRole('group', { name: 'Cendien message' })).toHaveTextContent(
    'I inspect the stairwell.',
  );

  await waitFor(() => {
    expect(global.fetch.mock.calls.some(([, options]) => options?.method === 'PUT')).toBe(true);
  });
  const putCall = global.fetch.mock.calls.find(([, options]) => options?.method === 'PUT');
  expect(JSON.parse(putCall[1].body)).toEqual({
    role: 'user',
    text: '[[DMB-SPEAKER:player-one:Cendien]] I inspect the stairwell.',
  });
});

test('routes concurrent audio and typed turns through the shared response scheduler', async () => {
  useConfirmedSpeakerSession();
  Object.assign(mockVoice, { status: 'listening', isConnected: true, muted: true });
  render(<App />);

  fireEvent.click(await screen.findByRole('button', { name: 'Juicebox microphone' }));
  mockSendEvent.mockClear();
  mockRequestResponse.mockClear();

  act(() => {
    mockVoiceOptions.onEvent({
      type: 'input_audio_buffer.speech_started',
      item_id: 'audio-turn-queued',
    });
    mockVoiceOptions.onEvent({
      type: 'conversation.item.created',
      item: {
        id: 'audio-turn-queued',
        type: 'message',
        role: 'user',
        content: [{ type: 'input_audio', audio: null }],
      },
    });
  });
  expect(mockRequestResponse).toHaveBeenCalledWith('audio:audio-turn-queued');

  fireEvent.change(screen.getByLabelText(/message input/i), {
    target: { value: 'I cover the stair while Juicebox moves.' },
  });
  fireEvent.click(screen.getByRole('button', { name: /send message/i }));

  expect(mockRequestResponse).toHaveBeenCalledTimes(2);
  expect(mockRequestResponse.mock.calls[1][0]).toMatch(/^typed:typed-/);
  expect(mockSendEvent.mock.calls.some(([event]) => event.type === 'response.create')).toBe(false);

  act(() => mockVoiceOptions.onEvent({
    type: 'conversation.item.added',
    item: {
      id: 'audio-turn-queued',
      type: 'message',
      role: 'user',
      content: [{ type: 'input_audio', audio: null }],
    },
  }));
  expect(mockRequestResponse).toHaveBeenCalledTimes(2);
});

test('routes a resolved physical roll through the same keyed response scheduler', async () => {
  useConfirmedSpeakerSession();
  Object.assign(mockVoice, { status: 'listening', isConnected: true, muted: true });
  render(<App />);
  await screen.findByRole('button', { name: 'Cendien microphone' });
  mockSendEvent.mockClear();
  mockRequestResponse.mockClear();

  act(() => window.dispatchEvent(new window.CustomEvent('dmb:physical-roll-resolved', {
    detail: {
      roll_id: 'roll-scheduler-1',
      player_id: 'player-one',
      roll_kind: 'skill',
      check_key: 'perception',
      natural_roll: 14,
      total: 19,
      success: true,
      natural_20: false,
      natural_1: false,
      dc_visibility: 'public',
      target_total: 15,
    },
  })));

  expect(mockSendEvent).toHaveBeenCalledWith(expect.objectContaining({
    type: 'conversation.item.create',
    item: expect.objectContaining({ role: 'user' }),
  }));
  expect(mockRequestResponse).toHaveBeenCalledWith('physical-roll:roll-scheduler-1');
  expect(mockSendEvent.mock.calls.some(([event]) => event.type === 'response.create')).toBe(false);
  const ledgerEvent = mockSendEvent.mock.calls
    .map(([event]) => event)
    .find((event) => event.item?.content?.[0]?.text?.startsWith('AUTHORITATIVE GAME LEDGER EVENT'));
  expect(ledgerEvent.item.content[0].text).toContain('"dc_visibility":"public"');
  expect(ledgerEvent.item.content[0].text).toContain('"target_total":15');
});

test('never includes a private target in the model-facing roll event', async () => {
  useConfirmedSpeakerSession();
  Object.assign(mockVoice, { status: 'listening', isConnected: true, muted: true });
  render(<App />);
  await screen.findByRole('button', { name: 'Cendien microphone' });
  mockSendEvent.mockClear();

  act(() => window.dispatchEvent(new window.CustomEvent('dmb:physical-roll-resolved', {
    detail: {
      roll_id: 'roll-private-target',
      player_id: 'player-one',
      roll_kind: 'skill',
      check_key: 'perception',
      natural_roll: 8,
      total: 13,
      success: false,
      natural_20: false,
      natural_1: false,
      dc_visibility: 'private',
      target_total: 30,
    },
  })));

  const ledgerEvent = mockSendEvent.mock.calls
    .map(([event]) => event)
    .find((event) => event.item?.content?.[0]?.text?.startsWith('AUTHORITATIVE GAME LEDGER EVENT'));
  expect(ledgerEvent.item.content[0].text).toContain('"dc_visibility":"private"');
  expect(ledgerEvent.item.content[0].text).not.toContain('target_total');
});

test('restores the active dynamic session and its Chronicle from local storage', async () => {
  const restoredSessionId = 'one-shot-restored';
  window.localStorage.setItem(ACTIVE_SESSION_STORAGE_KEY, restoredSessionId);
  const restoredSnapshot = {
    ...emptyPartySnapshot,
    session_id: restoredSessionId,
    players: emptyPartySnapshot.players.map((player) => ({
      ...player,
      character_status: 'confirmed',
    })),
  };
  global.fetch = jest.fn(async (url) => {
    if (String(url).endsWith(`/api/sessions/${restoredSessionId}/view`)) {
      return jsonResponse(restoredSnapshot);
    }
    if (String(url).endsWith(`/api/sessions/${restoredSessionId}/conversation`)) {
      return jsonResponse({
        session_id: restoredSessionId,
        messages: [{
          message_id: 'assistant:before-reload',
          role: 'assistant',
          text: 'The magistrate folds his hands and waits.',
          created_at: '2026-07-09T18:30:00Z',
        }],
      });
    }
    throw new Error(`Unexpected test request: ${url}`);
  });

  render(<App />);

  expect(await screen.findByText('The magistrate folds his hands and waits.'))
    .toBeInTheDocument();
  expect(screen.getByText('Live character sheets')).toBeInTheDocument();
  expect(global.fetch).not.toHaveBeenCalledWith(
    expect.stringContaining('/api/sessions/latest'),
    expect.anything(),
  );
  expect(window.localStorage.getItem(ACTIVE_SESSION_STORAGE_KEY)).toBe(restoredSessionId);
});

test('recovers the latest server session when local storage has never been populated', async () => {
  const latestSessionId = 'one-shot-first-rollout';
  const latestSnapshot = {
    ...emptyPartySnapshot,
    session_id: latestSessionId,
  };
  global.fetch = jest.fn(async (url) => {
    if (String(url).endsWith('/api/sessions/latest')) {
      return jsonResponse(latestSnapshot);
    }
    if (String(url).endsWith(`/api/sessions/${latestSessionId}/view`)) {
      return jsonResponse(latestSnapshot);
    }
    if (String(url).endsWith(`/api/sessions/${latestSessionId}/conversation`)) {
      return jsonResponse({ session_id: latestSessionId, messages: [] });
    }
    throw new Error(`Unexpected test request: ${url}`);
  });

  render(<App />);

  await waitFor(() => {
    expect(screen.getByRole('button', { name: /begin voice adventure/i })).toBeEnabled();
  });
  expect(window.localStorage.getItem(ACTIVE_SESSION_STORAGE_KEY)).toBe(latestSessionId);
  expect(global.fetch.mock.calls.some(([, options]) => options?.method === 'POST')).toBe(false);
});

test('prefers a newer dynamic server session over a stale stored guided ID', async () => {
  const latestSessionId = 'one-shot-pre-guided-storage-fix';
  window.localStorage.setItem(ACTIVE_SESSION_STORAGE_KEY, 'guided-one-shot-v2');
  const latestSnapshot = {
    ...emptyPartySnapshot,
    session_id: latestSessionId,
  };
  global.fetch = jest.fn(async (url) => {
    if (String(url).endsWith('/api/sessions/latest')) {
      return jsonResponse(latestSnapshot);
    }
    if (String(url).endsWith(`/api/sessions/${latestSessionId}/view`)) {
      return jsonResponse(latestSnapshot);
    }
    if (String(url).endsWith(`/api/sessions/${latestSessionId}/conversation`)) {
      return jsonResponse({
        session_id: latestSessionId,
        messages: [{
          message_id: 'assistant:latest-session-proof',
          role: 'assistant',
          text: 'The current one-shot is still here.',
          created_at: '2026-07-09T18:30:00Z',
        }],
      });
    }
    throw new Error(`Unexpected test request: ${url}`);
  });

  render(<App />);

  expect(await screen.findByText('The current one-shot is still here.'))
    .toBeInTheDocument();
  expect(window.localStorage.getItem(ACTIVE_SESSION_STORAGE_KEY)).toBe(latestSessionId);
  expect(global.fetch.mock.calls.some(([url]) => (
    String(url).includes('/guided-one-shot-v2/view')
  ))).toBe(false);
});

test('persists a finalized voice transcript once and never saves its partial draft', async () => {
  render(<App />);
  await waitFor(() => {
    expect(screen.getByRole('button', { name: /begin voice adventure/i })).toBeEnabled();
  });

  act(() => {
    mockVoiceOptions.onTranscript([{
      id: 'user:spoken-turn-1',
      role: 'user',
      text: 'I inspect',
      final: false,
    }]);
  });
  expect(global.fetch.mock.calls.filter(([, options]) => options?.method === 'PUT'))
    .toHaveLength(0);

  const finalized = [{
    id: 'user:spoken-turn-1',
    role: 'user',
    text: 'I inspect the magistrate for signs of fear.',
    final: true,
  }];
  act(() => {
    mockVoiceOptions.onTranscript(finalized);
    mockVoiceOptions.onTranscript(finalized);
  });

  await waitFor(() => {
    expect(global.fetch.mock.calls.filter(([, options]) => options?.method === 'PUT'))
      .toHaveLength(1);
  });
  const putCall = global.fetch.mock.calls.find(([, options]) => options?.method === 'PUT');
  expect(putCall[0]).toContain('/conversation/messages/user%3Aspoken-turn-1');
  expect(JSON.parse(putCall[1].body)).toEqual({
    role: 'user',
    text: 'I inspect the magistrate for signs of fear.',
  });
});

test('injects restored Chronicle context before the first response on reconnect', async () => {
  const restoredSessionId = 'one-shot-resume-order';
  window.localStorage.setItem(ACTIVE_SESSION_STORAGE_KEY, restoredSessionId);
  global.fetch = jest.fn(async (url) => {
    if (String(url).endsWith(`/api/sessions/${restoredSessionId}/view`)) {
      return jsonResponse({ ...emptyPartySnapshot, session_id: restoredSessionId });
    }
    if (String(url).endsWith(`/api/sessions/${restoredSessionId}/conversation`)) {
      return jsonResponse({
        session_id: restoredSessionId,
        messages: [
          {
            message_id: 'user:resume-1',
            role: 'user',
            text: 'I ask what the magistrate is hiding.',
            created_at: '2026-07-09T18:30:00Z',
          },
          {
            message_id: 'assistant:resume-2',
            role: 'assistant',
            text: 'His gaze flicks toward the locked drawer.',
            created_at: '2026-07-09T18:30:05Z',
          },
        ],
      });
    }
    throw new Error(`Unexpected test request: ${url}`);
  });

  const view = render(<App />);
  expect(await screen.findByText('His gaze flicks toward the locked drawer.'))
    .toBeInTheDocument();
  mockSendEvent.mockClear();
  mockRequestResponse.mockClear();
  Object.assign(mockVoice, { status: 'listening', isConnected: true });
  view.rerender(<App />);

  await waitFor(() => expect(mockSendEvent).toHaveBeenCalledTimes(1));
  expect(mockSendEvent.mock.calls[0][0]).toMatchObject({
    type: 'conversation.item.create',
    item: {
      type: 'message',
      role: 'user',
      content: [{
        type: 'input_text',
        text: expect.stringMatching(new RegExp(`^${SESSION_RESUME_PREFIX}`)),
      }],
    },
  });
  expect(mockRequestResponse).toHaveBeenCalledWith(`opening:${restoredSessionId}`);
});

test('Clear Chronicle removes both the visible and persisted conversation', async () => {
  render(<App />);
  await waitFor(() => {
    expect(screen.getByRole('button', { name: /begin voice adventure/i })).toBeEnabled();
  });
  act(() => {
    mockVoiceOptions.onTranscript([{
      id: 'assistant:clear-me',
      role: 'assistant',
      text: 'This entry will be cleared.',
      final: true,
    }]);
  });
  expect(await screen.findByText('This entry will be cleared.')).toBeInTheDocument();
  await waitFor(() => {
    expect(global.fetch.mock.calls.filter(([, options]) => options?.method === 'PUT'))
      .toHaveLength(1);
  });

  fireEvent.click(screen.getByRole('button', { name: /clear the current conversation/i }));

  expect(screen.queryByText('This entry will be cleared.')).not.toBeInTheDocument();
  expect(mockClearTranscript).toHaveBeenCalledTimes(1);
  await waitFor(() => {
    expect(global.fetch.mock.calls.some(([url, options]) => (
      String(url).endsWith('/api/sessions/guided-one-shot-v2/conversation')
      && options?.method === 'DELETE'
    ))).toBe(true);
  });
});

test('keeps the active voice session mounted during character creation', async () => {
  Object.assign(mockVoice, { status: 'listening', isConnected: true });
  render(<App />);

  const setupButton = await screen.findByRole('button', { name: /create or import your party/i });
  await waitFor(() => expect(setupButton).toBeEnabled());
  mockSendEvent.mockClear();
  fireEvent.click(setupButton);

  expect(screen.getByLabelText(/character setup/i)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /end voice/i })).toBeInTheDocument();
  expect(screen.getByText(/marin stays at the table/i)).toBeInTheDocument();
  expect(mockDisconnect).not.toHaveBeenCalled();
});

test('hands confirmed characters back to the connected DM exactly once', async () => {
  Object.assign(mockVoice, { status: 'listening', isConnected: true });
  const gameStateChanged = jest.fn();
  window.addEventListener('dmb:game-state-changed', gameStateChanged);

  render(<App />);
  const setupButton = await screen.findByRole('button', { name: /create or import your party/i });
  await waitFor(() => expect(setupButton).toBeEnabled());
  fireEvent.click(setupButton);
  mockSendEvent.mockClear();
  mockRequestResponse.mockClear();
  fireEvent.click(screen.getByRole('button', { name: /confirm test characters/i }));

  await waitFor(() => expect(screen.getByText('Live character sheets')).toBeInTheDocument());
  expect(gameStateChanged).toHaveBeenCalledTimes(1);
  await waitFor(() => expect(mockSendEvent).toHaveBeenCalledTimes(1));
  expect(mockSendEvent.mock.calls[0][0]).toMatchObject({
    type: 'conversation.item.create',
    item: {
      role: 'user',
      content: [{
        type: 'input_text',
        text: expect.stringContaining('both adventurers are confirmed'),
      }],
    },
  });
  expect(mockRequestResponse).toHaveBeenCalledWith('characters-confirmed:guided-one-shot-v2');

  window.removeEventListener('dmb:game-state-changed', gameStateChanged);
});
