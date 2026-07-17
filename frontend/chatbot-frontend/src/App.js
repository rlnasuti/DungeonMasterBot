import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import './App.css';
import ChatWindow from './components/ChatWindow';
import Composer from './components/Composer';
import DungeonMasterPortrait from './avatar/DungeonMasterPortrait';
import { CharacterPanel, CharacterSetup } from './character';
import { VoiceDungeonMaster, VOICE_STATES } from './voice';
import { createGameToolExecutor } from './gameToolExecutor';
import {
  clearConversation,
  readConversation,
  writeConversationMessage,
} from './conversation/api';
import { buildSessionResumeContext } from './conversation/resumeContext';
import {
  decodePersistedSpeakerText,
  encodePersistedSpeakerText,
  microphoneMutedControlEvent,
  rememberTurnSpeaker,
  speakerForTranscriptEntry,
  speakerOptionsFromPlayers,
  speakerSelectionControlEvent,
  speakerTurnControlEvent,
} from './voice/speakerIdentity';

const API_BASE = (process.env.REACT_APP_API_BASE || 'http://localhost:8000').replace(/\/$/, '');
const GUIDED_SESSION_ID = 'guided-one-shot-v2';
export const ACTIVE_SESSION_STORAGE_KEY = 'dungeon-master-bot.active-session-id';
const SAFE_SESSION_ID = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/;
const DEFAULT_PARTY_PLAYERS = Object.freeze([
  { player_id: 'player-one', display_name: 'Player One', seat: 1, character_status: 'empty' },
  { player_id: 'player-two', display_name: 'Player Two', seat: 2, character_status: 'empty' },
]);
const AUDIO_ITEM_EVENT_TYPES = new Set([
  'conversation.item.created',
  'conversation.item.added',
]);
const MAX_TRACKED_AUDIO_ITEMS = 256;

function addBounded(set, value, maximum = MAX_TRACKED_AUDIO_ITEMS) {
  set.add(value);
  while (set.size > maximum) set.delete(set.values().next().value);
}

function realtimeAudioItemId(event) {
  if (event?.type === 'input_audio_buffer.speech_started') {
    return typeof event.item_id === 'string' ? event.item_id : '';
  }
  if (!AUDIO_ITEM_EVENT_TYPES.has(event?.type)) return '';
  if (typeof event?.item?.id === 'string') return event.item.id;
  return typeof event?.item_id === 'string' ? event.item_id : '';
}

function isUserAudioConversationItem(event) {
  if (!AUDIO_ITEM_EVENT_TYPES.has(event?.type)) return false;
  const item = event?.item;
  return item?.type === 'message'
    && item?.role === 'user'
    && Array.isArray(item.content)
    && item.content.some((part) => part?.type === 'input_audio');
}

function readStoredSessionId(storage = window.localStorage) {
  try {
    const stored = storage?.getItem?.(ACTIVE_SESSION_STORAGE_KEY);
    return typeof stored === 'string' && SAFE_SESSION_ID.test(stored)
      ? stored
      : '';
  } catch (_error) {
    return '';
  }
}

function storeActiveSessionId(sessionId, storage = window.localStorage) {
  try {
    if (SAFE_SESSION_ID.test(sessionId)) {
      storage?.setItem?.(ACTIVE_SESSION_STORAGE_KEY, sessionId);
    }
  } catch (_error) {
    // Browsers with disabled storage still get a fully functional live session.
  }
}

function clearStoredSessionId(storage = window.localStorage) {
  try {
    storage?.removeItem?.(ACTIVE_SESSION_STORAGE_KEY);
  } catch (_error) {
    // Storage is an optional continuity aid, not a runtime dependency.
  }
}

function conversationMessageForUi(message) {
  const parsedTimestamp = Date.parse(message?.created_at || '');
  const persisted = message?.role === 'user' && message?.message_id?.startsWith('user:')
    ? decodePersistedSpeakerText(message.text)
    : { text: message.text, speaker: null };
  return {
    id: `history:${message.message_id}`,
    persistenceId: message.message_id,
    role: message.role === 'user' ? 'me' : 'dm',
    content: persisted.text,
    persistenceText: message.text,
    speaker: persisted.speaker,
    ts: Number.isNaN(parsedTimestamp) ? Date.now() : parsedTimestamp,
    final: true,
  };
}

function conversationMessagesForUi(payload) {
  if (!Array.isArray(payload?.messages)) return [];
  return payload.messages
    .filter((message) => (
      typeof message?.message_id === 'string'
      && message.message_id
      && (message.role === 'user' || message.role === 'assistant')
      && typeof message.text === 'string'
    ))
    .map(conversationMessageForUi);
}

function persistenceIdForUiMessage(message) {
  if (typeof message?.persistenceId === 'string' && message.persistenceId) {
    return message.persistenceId;
  }
  if (typeof message?.id !== 'string' || !message.id) return '';
  return message.id.startsWith('voice:') ? message.id.slice(6) : message.id;
}

async function readPartySession(sessionId) {
  const response = await fetch(`${API_BASE}/api/sessions/${encodeURIComponent(sessionId)}/view`, {
    headers: { Accept: 'application/json' },
  });
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const error = new Error(payload?.error?.message || 'The party ledger could not be read.');
    error.status = response.status;
    throw error;
  }
  return payload;
}

async function readLatestSessionId() {
  const response = await fetch(`${API_BASE}/api/sessions/latest`, {
    headers: { Accept: 'application/json' },
  });
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const error = new Error(payload?.error?.message || 'No recent party could be restored.');
    error.status = response.status;
    throw error;
  }
  if (!SAFE_SESSION_ID.test(payload?.session_id || '')) {
    const error = new Error('The recent party reference was invalid.');
    error.status = 404;
    throw error;
  }
  return payload.session_id;
}

async function createBlankPartySession(sessionId = `one-shot-${Date.now().toString(36)}`) {
  const response = await fetch(`${API_BASE}/api/sessions`, {
    method: 'POST',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: sessionId,
      idempotency_key: `web:create:${sessionId}`,
      players: [
        ...DEFAULT_PARTY_PLAYERS.map(({ player_id: playerId, display_name: displayName }) => ({
          player_id: playerId,
          display_name: displayName,
        })),
      ],
      public_world: {
        campaign: {
          campaign_id: 'the-bell-beneath-briar-glen',
          title: 'The Bell Beneath Briar Glen',
          current_scene: 'rainy-square',
          scene_title: 'The Toll in the Rain',
          revealed_facts: [],
        },
        npcs: {
          'mara-finch': {
            name: 'Mara Finch',
            description: 'A rain-soaked lantern-maker searching for her nephew.',
            visible_attitude: 'Frightened but hopeful',
            present: true,
          },
          'elian-voss': {
            name: 'Magistrate Elian Voss',
            description: 'An immaculate official offering a purse to destroy the bell.',
            visible_attitude: 'Civic-minded but guarded',
            present: true,
          },
        },
      },
    }),
  });
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(payload?.error?.message || 'A new party could not be created.');
  }
  return sessionId;
}

async function prepareGuidedPartySession() {
  await createBlankPartySession(GUIDED_SESSION_ID);
  // Creation idempotency intentionally replays the original response. Always
  // read the current snapshot so a completed party remains ready after reload.
  return readPartySession(GUIDED_SESSION_ID);
}

function hasConfirmedParty(snapshot) {
  return Array.isArray(snapshot?.players)
    && snapshot.players.length === 2
    && snapshot.players.every((player) => player.character_status === 'confirmed');
}

function VoiceControls({
  voice,
  sessionReady,
  speakerOptions,
  activeSpeakerId,
  onSpeakerChange,
}) {
  const canConnect = voice.status === VOICE_STATES.IDLE || voice.status === VOICE_STATES.ERROR;
  const connecting = voice.status === VOICE_STATES.CONNECTING;
  const activeSpeaker = speakerOptions.find((speaker) => speaker.playerId === activeSpeakerId);
  const [speakerError, setSpeakerError] = useState('');

  useEffect(() => {
    if (!voice.isConnected && activeSpeakerId) onSpeakerChange(null);
  }, [activeSpeakerId, onSpeakerChange, voice.isConnected]);

  useEffect(() => {
    if (activeSpeakerId && !activeSpeaker) {
      voice.setMuted(true);
      onSpeakerChange(null);
    }
  }, [activeSpeaker, activeSpeakerId, onSpeakerChange, voice]);

  if (canConnect || connecting) {
    return (
      <button
        type="button"
        className="voice-primary"
        onClick={voice.connect}
        disabled={!sessionReady || connecting}
      >
        {connecting ? 'Opening the story circle…' : 'Begin voice adventure'}
      </button>
    );
  }

  const selectSpeaker = (speaker) => {
    setSpeakerError('');
    voice.setMuted(true);
    if (speaker.playerId === activeSpeakerId) {
      onSpeakerChange(null);
      voice.sendEvent(microphoneMutedControlEvent());
      return;
    }

    onSpeakerChange(null);
    const control = speakerSelectionControlEvent(speaker);
    if (!control || !voice.sendEvent(control)) {
      setSpeakerError('The microphone stayed muted because speaker identity could not be attached.');
      return;
    }
    onSpeakerChange(speaker);
    voice.setMuted(false);
  };

  const endVoice = () => {
    voice.setMuted(true);
    onSpeakerChange(null);
    voice.disconnect();
  };

  return (
    <div className="voice-connected-controls">
      <div className="voice-speaker-switch" role="group" aria-label="Choose who is speaking">
        {speakerOptions.map((speaker) => {
          const active = speaker.playerId === activeSpeakerId;
          return (
            <button
              type="button"
              key={speaker.playerId}
              className={`voice-speaker-button${active ? ' voice-speaker-button--active' : ''}`}
              aria-pressed={active}
              aria-label={`${speaker.label} microphone`}
              title={active ? `Mute ${speaker.label}` : `Let ${speaker.label} speak`}
              onClick={() => selectSpeaker(speaker)}
            >
              <span className="voice-speaker-dot" aria-hidden="true" />
              {speaker.label}
            </button>
          );
        })}
      </div>
      <p className="voice-mic-status" role="status">
        {activeSpeaker
          ? `${activeSpeaker.label} microphone is live. Select again to mute.`
          : 'Microphone muted. Choose a character to speak.'}
      </p>
      {speakerError && <p className="voice-error" role="alert">{speakerError}</p>}
      <button type="button" className="voice-end" onClick={endVoice}>End voice</button>
    </div>
  );
}

function VoiceWorkspace({
  voice,
  sessionId,
  sessionReady,
  sessionError,
  messages,
  setMessages,
  partyReady,
  setupMode,
  resumeContext,
  onFinalMessage,
  onClearChronicle,
  onStartCharacterSetup,
  onCharacterSetupComplete,
  speakerOptions,
  activeSpeakerId,
  onSpeakerChange,
  onVoiceEventSender,
  onVoiceResponseRequester,
  onVoiceGateReset,
}) {
  const [input, setInput] = useState('');
  const [partyRailOpen, setPartyRailOpen] = useState(true);
  const inputRef = useRef(null);
  const openingRequestedRef = useRef(false);
  const { isConnected, requestResponse, sendEvent } = voice;

  useEffect(() => {
    onVoiceEventSender(sendEvent);
    return () => onVoiceEventSender(null);
  }, [onVoiceEventSender, sendEvent]);

  useEffect(() => {
    onVoiceResponseRequester(requestResponse);
    return () => onVoiceResponseRequester(null);
  }, [onVoiceResponseRequester, requestResponse]);

  useEffect(() => {
    if (!isConnected) onVoiceGateReset();
  }, [isConnected, onVoiceGateReset]);

  useEffect(() => {
    if (!isConnected) {
      openingRequestedRef.current = false;
      return;
    }
    if (!openingRequestedRef.current) {
      if (resumeContext) {
        const contextAccepted = sendEvent({
          type: 'conversation.item.create',
          item: {
            type: 'message',
            role: 'user',
            content: [{ type: 'input_text', text: resumeContext }],
          },
        });
        if (!contextAccepted) return;
      }
      if (requestResponse(`opening:${sessionId}`)) {
        openingRequestedRef.current = true;
      }
    }
  }, [isConnected, requestResponse, resumeContext, sendEvent, sessionId]);

  useEffect(() => {
    const announcePhysicalRoll = (event) => {
      const result = event.detail;
      if (!result || typeof result.natural_roll !== 'number') return;
      const chronicleMessage = {
        id: `roll:${result.roll_id}`,
        persistenceId: `roll:${result.roll_id}`,
        role: 'me',
        content: `Physical d20: ${result.natural_roll} · total ${result.total}`,
        ts: Date.now(),
        final: true,
      };
      setMessages((current) => [
        ...current.filter((message) => message.id !== `roll:${result.roll_id}`),
        chronicleMessage,
      ]);
      onFinalMessage({
        messageId: chronicleMessage.id,
        role: 'user',
        text: chronicleMessage.content,
      });
      if (!isConnected) return;
      const dcVisibility = result.dc_visibility === 'public'
        || result.dc_visibility === 'private'
        ? result.dc_visibility
        : null;
      const candidateTargetTotal = result.target_total === undefined || result.target_total === null
        || result.target_total === ''
        ? null
        : Number(result.target_total);
      const publicTargetTotal = dcVisibility === 'public'
        && Number.isInteger(candidateTargetTotal) && candidateTargetTotal > 0
        ? candidateTargetTotal
        : null;
      const authoritativeEvent = {
        type: 'physical_roll_resolved',
        player_id: result.player_id,
        roll_kind: result.roll_kind,
        check_key: result.check_key,
        natural_roll: result.natural_roll,
        total: result.total,
        success: result.success,
        natural_20: result.natural_20,
        natural_1: result.natural_1,
        ...(dcVisibility ? { dc_visibility: dcVisibility } : {}),
        ...(publicTargetTotal !== null ? { target_total: publicTargetTotal } : {}),
      };
      const accepted = sendEvent({
        type: 'conversation.item.create',
        item: {
          type: 'message',
          role: 'user',
          content: [{
            type: 'input_text',
            text: `AUTHORITATIVE GAME LEDGER EVENT: ${JSON.stringify(authoritativeEvent)}. Continue from this committed result; never invent or request a replacement roll.`,
          }],
        },
      });
      if (accepted) requestResponse(`physical-roll:${result.roll_id}`);
    };
    window.addEventListener('dmb:physical-roll-resolved', announcePhysicalRoll);
    return () => window.removeEventListener('dmb:physical-roll-resolved', announcePhysicalRoll);
  }, [isConnected, onFinalMessage, requestResponse, sendEvent, setMessages]);

  useEffect(() => {
    const announceConfirmedCharacters = () => {
      if (!isConnected) return;
      const accepted = sendEvent({
        type: 'conversation.item.create',
        item: {
          type: 'message',
          role: 'user',
          content: [{
            type: 'input_text',
            text: 'AUTHORITATIVE GAME LEDGER EVENT: Character setup is complete and both adventurers are confirmed. Read the current public game state, introduce the confirmed party, and then begin the campaign opening.',
          }],
        },
      });
      if (accepted) requestResponse(`characters-confirmed:${sessionId}`);
    };
    window.addEventListener('dmb:characters-confirmed', announceConfirmedCharacters);
    return () => window.removeEventListener('dmb:characters-confirmed', announceConfirmedCharacters);
  }, [isConnected, requestResponse, sendEvent, sessionId]);

  const handleSend = useCallback(() => {
    const text = input.trim();
    if (!text || !voice.isConnected) return;

    const itemId = `typed-${Date.now()}`;
    const accepted = voice.sendEvent({
      type: 'conversation.item.create',
      item: {
        id: itemId,
        type: 'message',
        role: 'user',
        content: [{ type: 'input_text', text }],
      },
    });
    if (!accepted || !voice.requestResponse(`typed:${itemId}`)) return;

    setMessages((current) => [
      ...current,
      {
        id: itemId,
        persistenceId: itemId,
        role: 'me',
        content: text,
        ts: Date.now(),
        final: true,
      },
    ]);
    onFinalMessage({ messageId: itemId, role: 'user', text });
    setInput('');
    window.requestAnimationFrame(() => inputRef.current?.focus());
  }, [input, onFinalMessage, setMessages, voice]);

  const handleClear = useCallback(() => {
    voice.clearTranscript();
    onClearChronicle();
    inputRef.current?.focus();
  }, [onClearChronicle, voice]);

  const portraitState = voice.muted ? 'muted' : voice.status;

  if (setupMode) {
    return (
      <main className="setup-page setup-page--with-voice">
        <div className="setup-page-heading setup-page-heading--voice">
          <div className="setup-voice-presence">
            <DungeonMasterPortrait state={portraitState} audioLevel={voice.audioLevel || 0} />
            <div>
              <p className="campaign-kicker">Before the first toll</p>
              <h1>Gather your party</h1>
              <p>Marin stays at the table while you ready both adventurers.</p>
            </div>
          </div>
          <div className="setup-voice-controls">
            <VoiceControls
              voice={voice}
              sessionReady={sessionReady}
              speakerOptions={speakerOptions}
              activeSpeakerId={activeSpeakerId}
              onSpeakerChange={onSpeakerChange}
            />
            <p className="voice-model">Voice engine · {voice.model}</p>
            {voice.error && <p className="voice-error" role="alert">{voice.error.message}</p>}
            {sessionError && <p className="voice-error" role="alert">{sessionError}</p>}
          </div>
        </div>
        <CharacterSetup
          sessionId={sessionId}
          apiBaseUrl={API_BASE}
          onComplete={onCharacterSetupComplete}
        />
      </main>
    );
  }

  return (
    <div className={`layout${partyRailOpen ? '' : ' layout--party-collapsed'}`}>
      <aside className="dm-rail" aria-label="Dungeon Master voice controls">
        <DungeonMasterPortrait state={portraitState} audioLevel={voice.audioLevel || 0} />

        <div className="voice-controls">
          <VoiceControls
            voice={voice}
            sessionReady={sessionReady}
            speakerOptions={speakerOptions}
            activeSpeakerId={activeSpeakerId}
            onSpeakerChange={onSpeakerChange}
          />
          <button
            type="button"
            className="voice-secondary"
            onClick={() => {
              if (partyReady) {
                voice.setMuted(true);
                onSpeakerChange(null);
                voice.disconnect();
                voice.clearTranscript();
              }
              onStartCharacterSetup();
            }}
            disabled={!sessionReady || voice.status === VOICE_STATES.CONNECTING}
          >
            {partyReady ? 'Start a new party' : 'Create or import your party'}
          </button>
          <p className="voice-model">Voice engine · {voice.model}</p>
          {voice.error && <p className="voice-error" role="alert">{voice.error.message}</p>}
          {sessionError && <p className="voice-error" role="alert">{sessionError}</p>}
        </div>

        <section className="campaign-card" aria-labelledby="campaign-title">
          <p className="campaign-kicker">Tonight&apos;s one-shot</p>
          <h1 id="campaign-title">The Bell Beneath Briar Glen</h1>
          <p>A rain-soaked mystery for two adventurers, built for roughly 45 minutes.</p>
          <ul>
            <li>Your choices steer the story.</li>
            <li>Roll your own physical dice.</li>
            <li>The app keeps the private ledger.</li>
          </ul>
        </section>
      </aside>

      <ChatWindow
        messages={messages}
        onClear={handleClear}
        emptyMessage={sessionReady
          ? 'Begin the voice adventure. Your spoken chronicle will appear here.'
          : 'Preparing the table…'}
      />

      <Composer
        value={input}
        setValue={setInput}
        onSend={handleSend}
        disabled={!voice.isConnected}
        inputRef={inputRef}
        placeholder={voice.isConnected
          ? 'Speak—or type when you need to…'
          : 'Begin voice adventure to speak or type…'}
      />

      <aside
        className={`character-rail${partyRailOpen ? '' : ' character-rail--collapsed'}`}
        aria-label="Live party state"
      >
        <header className="character-rail-header">
          <div className="character-rail-heading">
            <p>Character sheets</p>
            <h2>Live party state</h2>
          </div>
          <button
            type="button"
            className="party-rail-toggle"
            aria-controls="party-state-content"
            aria-expanded={partyRailOpen}
            aria-label={partyRailOpen ? 'Hide live party state' : 'Show live party state'}
            title={partyRailOpen ? 'Hide live party state' : 'Show live party state'}
            onClick={() => setPartyRailOpen((current) => !current)}
          >
            <span className="party-rail-toggle-icon" aria-hidden="true">
              {partyRailOpen ? '›' : '‹'}
            </span>
            <span className="party-rail-toggle-copy">
              {partyRailOpen ? 'Hide' : 'Show'}
            </span>
          </button>
        </header>

        <div
          id="party-state-content"
          className="character-rail-content"
          hidden={!partyRailOpen}
        >
          {sessionReady && partyReady ? (
            <CharacterPanel
              sessionId={sessionId}
              apiBaseUrl={API_BASE}
              pollIntervalMs={2500}
            />
          ) : sessionReady ? (
            <section className="party-awaiting" aria-label="Character sheets">
              <p className="character-eyebrow">The party ledger is empty</p>
              <h2>Your adventurers await</h2>
              <p>Begin the voice adventure, then open character creation when Marin invites you.</p>
            </section>
          ) : (
            <div className="character-loading" role="status">Preparing character ledgers…</div>
          )}
        </div>
      </aside>
    </div>
  );
}

function App() {
  const [sessionId, setSessionId] = useState(GUIDED_SESSION_ID);
  const [sessionReady, setSessionReady] = useState(false);
  const [sessionError, setSessionError] = useState('');
  const [partyReady, setPartyReady] = useState(false);
  const [partyPlayers, setPartyPlayers] = useState([]);
  const [activeSpeakerId, setActiveSpeakerId] = useState(null);
  const [setupMode, setSetupMode] = useState(false);
  const [messages, setMessages] = useState([]);
  const [audioLevel, setAudioLevel] = useState(0);
  const activeSessionIdRef = useRef(GUIDED_SESSION_ID);
  const renderedSessionIdRef = useRef(sessionId);
  const savedMessageKeysRef = useRef(new Set());
  const conversationOperationQueueRef = useRef(Promise.resolve());
  const activeSpeakerRef = useRef(null);
  const turnSpeakersRef = useRef(new Map());
  const taggedAudioItemsRef = useRef(new Set());
  const respondedAudioItemsRef = useRef(new Set());
  const voiceEventSenderRef = useRef(null);
  const voiceResponseRequesterRef = useRef(null);
  renderedSessionIdRef.current = sessionId;

  const speakerOptions = useMemo(
    () => speakerOptionsFromPlayers(partyPlayers),
    [partyPlayers],
  );

  const handleSpeakerChange = useCallback((speaker) => {
    activeSpeakerRef.current = speaker || null;
    setActiveSpeakerId(speaker?.playerId || null);
  }, []);

  useEffect(() => {
    if (!activeSpeakerId) return;
    const current = speakerOptions.find((speaker) => speaker.playerId === activeSpeakerId);
    activeSpeakerRef.current = current || null;
    if (!current) setActiveSpeakerId(null);
  }, [activeSpeakerId, speakerOptions]);

  const handleVoiceEventSender = useCallback((sender) => {
    voiceEventSenderRef.current = typeof sender === 'function' ? sender : null;
  }, []);

  const handleVoiceResponseRequester = useCallback((requester) => {
    voiceResponseRequesterRef.current = typeof requester === 'function' ? requester : null;
  }, []);

  const resetVoiceGate = useCallback(() => {
    activeSpeakerRef.current = null;
    turnSpeakersRef.current.clear();
    taggedAudioItemsRef.current.clear();
    respondedAudioItemsRef.current.clear();
    setActiveSpeakerId(null);
  }, []);

  const handleVoiceEvent = useCallback((event) => {
    const itemId = realtimeAudioItemId(event);
    if (!itemId) return;

    if (event.type === 'input_audio_buffer.speech_started') {
      const speaker = activeSpeakerRef.current;
      if (speaker) rememberTurnSpeaker(turnSpeakersRef.current, itemId, speaker);
      return;
    }

    if (!isUserAudioConversationItem(event)) return;
    const speaker = turnSpeakersRef.current.get(itemId);
    const sendEvent = voiceEventSenderRef.current;
    const requestResponse = voiceResponseRequesterRef.current;
    if (
      !speaker
      || !sendEvent
      || !requestResponse
      || respondedAudioItemsRef.current.has(itemId)
    ) return;

    if (!taggedAudioItemsRef.current.has(itemId)) {
      const speakerTag = speakerTurnControlEvent(speaker, itemId);
      if (!speakerTag || !sendEvent(speakerTag)) return;
      addBounded(taggedAudioItemsRef.current, itemId);
    }
    if (!requestResponse(`audio:${itemId}`)) return;
    addBounded(respondedAudioItemsRef.current, itemId);
  }, []);

  const enqueueConversationOperation = useCallback((operation) => {
    const pending = conversationOperationQueueRef.current
      .catch(() => {})
      .then(operation);
    conversationOperationQueueRef.current = pending.catch(() => {});
    return pending;
  }, []);

  const installSession = useCallback((nextSessionId, snapshot, conversation) => {
    const restoredMessages = conversationMessagesForUi(conversation);
    activeSpeakerRef.current = null;
    turnSpeakersRef.current.clear();
    taggedAudioItemsRef.current.clear();
    respondedAudioItemsRef.current.clear();
    activeSessionIdRef.current = nextSessionId;
    savedMessageKeysRef.current = new Set(restoredMessages.map(
      (message) => `${nextSessionId}\u0000${message.persistenceId}`,
    ));
    setSessionId(nextSessionId);
    setActiveSpeakerId(null);
    setPartyPlayers(Array.isArray(snapshot?.players) ? snapshot.players : []);
    setMessages((currentMessages) => {
      if (
        renderedSessionIdRef.current !== nextSessionId
        || !currentMessages.length
      ) {
        return restoredMessages;
      }

      // During a Fast Refresh, the browser can still hold finalized turns that
      // predate the persistence endpoints. Merge those player-visible turns so
      // the first rollout saves them instead of erasing them on bootstrap.
      const merged = [...restoredMessages];
      const knownIds = new Set(restoredMessages.map(persistenceIdForUiMessage));
      currentMessages.forEach((message) => {
        const persistenceId = persistenceIdForUiMessage(message);
        if (!persistenceId || knownIds.has(persistenceId)) return;
        knownIds.add(persistenceId);
        merged.push({ ...message, persistenceId });
      });
      return merged;
    });
    setPartyReady(hasConfirmedParty(snapshot));
    setSetupMode(false);
    storeActiveSessionId(nextSessionId);
  }, []);

  useEffect(() => {
    let cancelled = false;

    const loadExistingSession = async (candidateSessionId) => {
      const snapshot = await readPartySession(candidateSessionId);
      const conversation = await readConversation({
        sessionId: candidateSessionId,
        apiBaseUrl: API_BASE,
      });
      return { sessionId: candidateSessionId, snapshot, conversation };
    };

    const loadGuidedSession = async () => {
      const snapshot = await prepareGuidedPartySession();
      const conversation = await readConversation({
        sessionId: GUIDED_SESSION_ID,
        apiBaseUrl: API_BASE,
      });
      return { sessionId: GUIDED_SESSION_ID, snapshot, conversation };
    };

    const bootstrap = async () => {
      const storedSessionId = readStoredSessionId();
      // A dynamic session is an explicit user choice and wins. The original
      // guided ID is not strong evidence: an older hot-reloaded build may have
      // written it before the latest-session recovery endpoint existed.
      if (storedSessionId && storedSessionId !== GUIDED_SESSION_ID) {
        try {
          return await loadExistingSession(storedSessionId);
        } catch (error) {
          if (error?.status !== 404) throw error;
          clearStoredSessionId();
        }
      }

      try {
        const latestSessionId = await readLatestSessionId();
        return await loadExistingSession(latestSessionId);
      } catch (error) {
        if (error?.status !== 404) throw error;
      }

      return loadGuidedSession();
    };

    bootstrap()
      .then(({ sessionId: restoredSessionId, snapshot, conversation }) => {
        if (cancelled) return;
        installSession(restoredSessionId, snapshot, conversation);
        setSessionReady(true);
      })
      .catch((error) => {
        if (!cancelled) setSessionError(error.message);
      });
    return () => { cancelled = true; };
  }, [installSession]);

  const persistFinalMessage = useCallback((message) => {
    const nextMessageId = message?.messageId;
    const nextRole = message?.role;
    const nextText = message?.text;
    if (
      typeof nextMessageId !== 'string'
      || !nextMessageId
      || nextMessageId.length > 200
      || (nextRole !== 'user' && nextRole !== 'assistant')
      || typeof nextText !== 'string'
      || !nextText.trim()
    ) {
      return false;
    }

    const targetSessionId = activeSessionIdRef.current;
    const persistenceKey = `${targetSessionId}\u0000${nextMessageId}`;
    if (savedMessageKeysRef.current.has(persistenceKey)) return false;
    savedMessageKeysRef.current.add(persistenceKey);

    void enqueueConversationOperation(() => writeConversationMessage({
      sessionId: targetSessionId,
      messageId: nextMessageId,
      role: nextRole,
      text: nextText,
      apiBaseUrl: API_BASE,
    })).catch(() => {
      savedMessageKeysRef.current.delete(persistenceKey);
      setSessionError('A Chronicle entry could not be saved. Voice play can continue.');
    });
    return true;
  }, [enqueueConversationOperation]);

  const handleClearChronicle = useCallback(() => {
    const targetSessionId = activeSessionIdRef.current;
    setMessages([]);
    turnSpeakersRef.current.clear();
    taggedAudioItemsRef.current.clear();
    respondedAudioItemsRef.current.clear();
    savedMessageKeysRef.current = new Set();
    void enqueueConversationOperation(() => clearConversation({
      sessionId: targetSessionId,
      apiBaseUrl: API_BASE,
    })).catch(() => {
      setSessionError('The Chronicle could not be cleared from persistent storage.');
    });
  }, [enqueueConversationOperation]);

  useEffect(() => {
    if (!sessionReady) return;
    messages.forEach((message) => {
      if (!message?.final) return;
      persistFinalMessage({
        messageId: persistenceIdForUiMessage(message),
        role: message.role === 'me' ? 'user' : 'assistant',
        text: message.persistenceText || message.content,
      });
    });
  }, [messages, persistFinalMessage, sessionReady]);

  const toolExecutor = useMemo(
    () => createGameToolExecutor({ sessionId, apiBase: API_BASE }),
    [sessionId],
  );

  const startCharacterSetup = useCallback(async () => {
    if (!partyReady) {
      setSetupMode(true);
      return;
    }

    setSessionReady(false);
    setSessionError('');
    try {
      const nextSessionId = await createBlankPartySession();
      activeSessionIdRef.current = nextSessionId;
      activeSpeakerRef.current = null;
      turnSpeakersRef.current.clear();
      taggedAudioItemsRef.current.clear();
      respondedAudioItemsRef.current.clear();
      savedMessageKeysRef.current = new Set();
      setMessages([]);
      setSessionId(nextSessionId);
      setActiveSpeakerId(null);
      setPartyPlayers(DEFAULT_PARTY_PLAYERS.map((player) => ({ ...player })));
      storeActiveSessionId(nextSessionId);
      setPartyReady(false);
      setSetupMode(true);
      setSessionReady(true);
    } catch (error) {
      setSessionError(error.message);
      setSessionReady(true);
    }
  }, [partyReady]);

  const handleCharacterSetupComplete = useCallback((summary) => {
    if (Array.isArray(summary?.players)) {
      setPartyPlayers(summary.players.map((player, index) => ({
        ...player,
        seat: index + 1,
        character_status: 'confirmed',
        character: player.character || { name: player.character_name },
      })));
    }
    setPartyReady(true);
    setSetupMode(false);
    window.dispatchEvent(new window.Event('dmb:game-state-changed'));
    window.dispatchEvent(new window.CustomEvent('dmb:characters-confirmed', {
      detail: summary,
    }));
  }, []);

  const handleTranscript = useCallback((transcript) => {
    setMessages((current) => {
      const next = [...current];
      transcript.forEach((entry) => {
        const id = `voice:${entry.id}`;
        const existingIndex = next.findIndex((message) => message.id === id);
        const speaker = speakerForTranscriptEntry(entry, turnSpeakersRef.current)
          || (existingIndex >= 0 ? next[existingIndex].speaker : null);
        const persistenceText = entry.role === 'user'
          ? encodePersistedSpeakerText(entry.text, speaker)
          : entry.text;
        const normalized = {
          id,
          persistenceId: entry.id,
          role: entry.role === 'user' ? 'me' : 'dm',
          content: entry.text,
          persistenceText,
          speaker,
          final: entry.final,
          ts: existingIndex >= 0 ? next[existingIndex].ts : Date.now(),
        };
        if (existingIndex >= 0) next[existingIndex] = normalized;
        else next.push(normalized);
      });
      return next;
    });
    transcript.forEach((entry) => {
      if (!entry.final) return;
      const speaker = speakerForTranscriptEntry(entry, turnSpeakersRef.current);
      persistFinalMessage({
        messageId: entry.id,
        role: entry.role === 'user' ? 'user' : 'assistant',
        text: entry.role === 'user'
          ? encodePersistedSpeakerText(entry.text, speaker)
          : entry.text,
      });
    });
  }, [persistFinalMessage]);

  const resumeContext = useMemo(
    () => buildSessionResumeContext(messages),
    [messages],
  );

  return (
    <VoiceDungeonMaster
      onTranscript={handleTranscript}
      onAudioLevel={setAudioLevel}
      onEvent={handleVoiceEvent}
      onToolCall={toolExecutor}
    >
      {(voice) => (
        <VoiceWorkspace
          voice={{ ...voice, audioLevel }}
          sessionId={sessionId}
          sessionReady={sessionReady}
          sessionError={sessionError}
          messages={messages}
          setMessages={setMessages}
          partyReady={partyReady}
          setupMode={setupMode}
          resumeContext={resumeContext}
          onFinalMessage={persistFinalMessage}
          onClearChronicle={handleClearChronicle}
          onStartCharacterSetup={startCharacterSetup}
          onCharacterSetupComplete={handleCharacterSetupComplete}
          speakerOptions={speakerOptions}
          activeSpeakerId={activeSpeakerId}
          onSpeakerChange={handleSpeakerChange}
          onVoiceEventSender={handleVoiceEventSender}
          onVoiceResponseRequester={handleVoiceResponseRequester}
          onVoiceGateReset={resetVoiceGate}
        />
      )}
    </VoiceDungeonMaster>
  );
}

export default App;
