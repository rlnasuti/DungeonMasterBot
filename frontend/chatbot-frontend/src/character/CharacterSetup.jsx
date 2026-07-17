import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createGameApi } from './api';
import {
  buildTemplateCharacter,
  CHARACTER_TEMPLATE_OPTIONS,
  projectPublicImportedCharacter,
} from './characterTemplates';
import './character.css';

let attemptSequence = 0;

function nextAttemptId() {
  attemptSequence += 1;
  return `${Date.now().toString(36)}-${attemptSequence}`;
}

function normalizePlayer(player, index) {
  const playerId = player.player_id ?? player.id;
  if (!playerId) throw new Error(`Player ${index + 1} is missing a player_id.`);
  const displayName = player.display_name || player.displayName || `Player ${index + 1}`;
  return {
    playerId: String(playerId),
    displayName,
    persistedDisplayName: displayName,
    characterName: player.character?.name || '',
    className: player.character?.class_name || '',
    templateId: index === 0 ? 'fighter' : 'wizard',
    importPayload: null,
    importFileName: '',
    importError: '',
    mode: 'template',
    status: player.character_status || (player.character ? 'confirmed' : 'empty'),
  };
}

function formFieldName(playerId, field) {
  return `player:${encodeURIComponent(playerId)}:${field}`;
}

function snapshotFormDrafts(form, drafts) {
  const formData = new FormData(form);
  return drafts.map((draft) => {
    const fieldValue = (field, fallback) => {
      const value = formData.get(formFieldName(draft.playerId, field));
      return typeof value === 'string' ? value : fallback;
    };
    return {
      ...draft,
      displayName: fieldValue('displayName', draft.displayName),
      characterName: fieldValue('characterName', draft.characterName),
      templateId: fieldValue('templateId', draft.templateId),
    };
  });
}

function readLocalCharacterFile(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error('The selected JSON file could not be read.'));
    reader.onload = () => {
      try {
        resolve(projectPublicImportedCharacter(JSON.parse(reader.result)));
      } catch (error) {
        reject(error instanceof Error ? error : new Error('The selected file is not valid JSON.'));
      }
    };
    reader.readAsText(file);
  });
}

function buildSubmissionCharacter(draft) {
  if (draft.mode === 'import') {
    return { ...draft.importPayload, name: draft.characterName.trim() };
  }
  return buildTemplateCharacter(draft.templateId, draft.playerId, draft.characterName);
}

function shouldPersistDisplayName(draft, index) {
  const displayName = draft.displayName.trim();
  const word = index === 0 ? 'One' : 'Two';
  const placeholders = new Set([`player ${index + 1}`, `player ${word.toLowerCase()}`]);
  return !placeholders.has(displayName.toLowerCase())
    && displayName !== draft.persistedDisplayName.trim();
}

export default function CharacterSetup({
  sessionId,
  players: suppliedPlayers,
  api: suppliedApi,
  apiBaseUrl = 'http://localhost:8000',
  onComplete = () => {},
  className = '',
}) {
  const api = useMemo(
    () => suppliedApi || createGameApi(apiBaseUrl),
    [apiBaseUrl, suppliedApi],
  );
  const [drafts, setDrafts] = useState([]);
  const [stateVersion, setStateVersion] = useState(null);
  const [loading, setLoading] = useState(Boolean(sessionId));
  const [submitting, setSubmitting] = useState(false);
  const [complete, setComplete] = useState(false);
  const [error, setError] = useState(null);
  const [progress, setProgress] = useState(null);
  const currentVersionRef = useRef(null);
  const attemptRef = useRef(null);

  useEffect(() => {
    if (!sessionId) {
      setLoading(false);
      setError(null);
      setDrafts([]);
      return undefined;
    }

    const controller = new AbortController();
    setLoading(true);
    setError(null);
    setComplete(false);
    attemptRef.current = null;

    api.getGameState(sessionId, { signal: controller.signal })
      .then((snapshot) => {
        if (controller.signal.aborted) return;
        const sourcePlayers = suppliedPlayers?.length ? suppliedPlayers : snapshot?.players;
        if (!Array.isArray(sourcePlayers) || sourcePlayers.length !== 2) {
          throw new Error('Character setup requires exactly two session players.');
        }
        const version = snapshot?.state_version;
        if (!Number.isInteger(version) || version < 0) {
          throw new Error('The game API did not provide a valid state_version.');
        }
        setDrafts(sourcePlayers.map(normalizePlayer));
        currentVersionRef.current = version;
        setStateVersion(version);
      })
      .catch((requestError) => {
        if (requestError?.name !== 'AbortError' && !controller.signal.aborted) {
          setError(requestError);
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [api, sessionId, suppliedPlayers]);

  const updateDraft = (index, patch) => {
    attemptRef.current = null;
    setProgress(null);
    setError(null);
    setDrafts((current) => current.map((draft, draftIndex) => (
      draftIndex === index ? { ...draft, ...patch } : draft
    )));
  };

  const handleImport = async (index, file) => {
    if (!file) return;
    updateDraft(index, { importError: '' });
    try {
      const imported = await readLocalCharacterFile(file);
      updateDraft(index, {
        mode: 'import',
        importPayload: imported,
        importFileName: file.name,
        importError: '',
        characterName: typeof imported.name === 'string' ? imported.name : '',
      });
    } catch (importError) {
      updateDraft(index, {
        mode: 'template',
        importPayload: null,
        importFileName: '',
        importError: importError.message,
      });
    }
  };

  const validateDrafts = (candidateDrafts) => {
    for (const [index, draft] of candidateDrafts.entries()) {
      if (!draft.displayName.trim()) return `Player ${index + 1} needs a display name.`;
      if (draft.status !== 'confirmed' && !draft.characterName.trim()) {
        return `${draft.displayName} needs a character name.`;
      }
      if (draft.mode === 'import' && !draft.importPayload) {
        return `${draft.displayName} needs a readable local JSON character file.`;
      }
    }
    return null;
  };

  const buildAttempt = (candidateDrafts) => {
    // User edits clear attemptRef. Internal status updates do not, so a retry
    // after a lost response replays the exact operation and idempotency key.
    if (attemptRef.current) return attemptRef.current;
    const characters = candidateDrafts.map((draft) => (
      draft.status === 'confirmed' ? null : buildSubmissionCharacter(draft)
    ));
    const signature = JSON.stringify({
      version: currentVersionRef.current,
      drafts: candidateDrafts.map((draft, index) => ({
        playerId: draft.playerId,
        displayName: draft.displayName.trim(),
        mode: draft.mode,
        status: draft.status,
        character: characters[index],
      })),
    });
    const attemptId = nextAttemptId();
    const steps = [];
    candidateDrafts.forEach((draft, index) => {
      if (shouldPersistDisplayName(draft, index)) {
        steps.push({
          type: 'identity',
          playerIndex: index,
          playerId: draft.playerId,
          displayName: draft.displayName.trim(),
          idempotencyKey: `character-setup:${attemptId}:${draft.playerId}:identity`,
        });
      }
      if (draft.status === 'confirmed') return;
      if (draft.status !== 'draft') {
        steps.push({
          type: 'stage',
          playerIndex: index,
          playerId: draft.playerId,
          character: characters[index],
          source: draft.mode === 'import' ? 'imported' : 'created',
          idempotencyKey: `character-setup:${attemptId}:${draft.playerId}:stage`,
        });
      }
      steps.push({
        type: 'confirm',
        playerIndex: index,
        playerId: draft.playerId,
        idempotencyKey: `character-setup:${attemptId}:${draft.playerId}:confirm`,
      });
    });
    attemptRef.current = {
      signature,
      steps,
      index: 0,
      version: currentVersionRef.current,
      drafts: candidateDrafts,
      characters,
    };
    return attemptRef.current;
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    // Read the committed controls at the submit boundary. React state remains
    // useful for rendering, but a native select may expose its new value just
    // before its change callback has updated that state.
    const submittedDrafts = snapshotFormDrafts(event.currentTarget, drafts);
    const validationMessage = validateDrafts(submittedDrafts);
    if (validationMessage) {
      setError(new Error(validationMessage));
      return;
    }

    const attempt = buildAttempt(submittedDrafts);
    setDrafts(submittedDrafts);
    setSubmitting(true);
    setError(null);
    try {
      while (attempt.index < attempt.steps.length) {
        const step = attempt.steps[attempt.index];
        const progressVerb = {
          identity: 'Saving name for',
          stage: 'Staging',
          confirm: 'Confirming',
        }[step.type];
        setProgress({
          completed: attempt.index,
          total: attempt.steps.length,
          label: `${progressVerb} ${attempt.drafts[step.playerIndex].displayName}`,
        });
        let response;
        if (step.type === 'identity') {
          response = await api.updatePlayerIdentity(sessionId, step.playerId, {
            display_name: step.displayName,
            expected_state_version: attempt.version,
            idempotency_key: step.idempotencyKey,
          });
          setDrafts((current) => current.map((draft, index) => (
            index === step.playerIndex
              ? { ...draft, persistedDisplayName: step.displayName }
              : draft
          )));
        } else if (step.type === 'stage') {
          response = await api.stageCharacter(sessionId, step.playerId, {
            character: step.character,
            source: step.source,
            expected_state_version: attempt.version,
            idempotency_key: step.idempotencyKey,
          });
          setDrafts((current) => current.map((draft, index) => (
            index === step.playerIndex ? { ...draft, status: 'draft' } : draft
          )));
        } else {
          response = await api.confirmCharacter(sessionId, step.playerId, {
            expected_state_version: attempt.version,
            idempotency_key: step.idempotencyKey,
          });
          setDrafts((current) => current.map((draft, index) => (
            index === step.playerIndex ? { ...draft, status: 'confirmed' } : draft
          )));
        }
        if (!Number.isInteger(response?.state_version)) {
          throw new Error('The game API did not return state_version after character setup.');
        }
        attempt.version = response.state_version;
        attempt.index += 1;
        currentVersionRef.current = response.state_version;
        setStateVersion(response.state_version);
      }

      setProgress({ completed: attempt.steps.length, total: attempt.steps.length, label: 'Setup complete' });
      setComplete(true);
      attemptRef.current = null;
      onComplete({
        session_id: sessionId,
        state_version: currentVersionRef.current,
        players: attempt.drafts.map((draft, index) => ({
          player_id: draft.playerId,
          display_name: draft.displayName.trim(),
          character_name: draft.characterName.trim(),
          class_name: attempt.characters[index]?.class_name || draft.className,
        })),
      });
    } catch (requestError) {
      setError(requestError);
    } finally {
      setSubmitting(false);
    }
  };

  if (!sessionId) {
    return (
      <section className={`character-setup character-panel-state ${className}`} aria-label="Character setup">
        <h2>Character setup</h2>
        <p>Select a game session before creating characters.</p>
      </section>
    );
  }

  if (loading) {
    return (
      <section className={`character-setup character-panel-state ${className}`} aria-label="Character setup" aria-busy="true">
        <p role="status">Loading player seats…</p>
      </section>
    );
  }

  if (!drafts.length) {
    return (
      <section className={`character-setup character-panel-state ${className}`} aria-label="Character setup">
        <div role="alert">
          <h2>Character setup unavailable</h2>
          <p>{error?.message || 'No player seats were returned by the game API.'}</p>
        </div>
      </section>
    );
  }

  return (
    <section className={`character-setup ${className}`} aria-labelledby="character-setup-title">
      <header className="character-setup-header">
        <div>
          <p className="character-eyebrow">Two-player one-shot</p>
          <h1 id="character-setup-title">Ready your adventurers</h1>
          <p>Choose a level 3 template or import a local character JSON for each player.</p>
        </div>
        <span>State v{stateVersion}</span>
      </header>

      <div className="character-import-notice">
        <strong>Local JSON character import</strong>
        <span>Upload a file from this device. This does not connect to or automate D&amp;D Beyond.</span>
      </div>

      <form onSubmit={handleSubmit}>
        <div className="character-setup-grid">
          {drafts.map((draft, index) => {
            const selectedTemplate = CHARACTER_TEMPLATE_OPTIONS.find((option) => option.value === draft.templateId);
            return (
              <fieldset key={draft.playerId} disabled={submitting || complete}>
                <legend>Player {index + 1}</legend>
                <label htmlFor={`setup-player-${index}-name`}>Player display name</label>
                <input
                  id={`setup-player-${index}-name`}
                  name={formFieldName(draft.playerId, 'displayName')}
                  value={draft.displayName}
                  onChange={(event) => updateDraft(index, { displayName: event.target.value })}
                  autoComplete="off"
                  required
                />
                <small>The session owns the player ID; this label is returned when setup completes.</small>

                <label htmlFor={`setup-character-${index}-name`}>Character name</label>
                <input
                  id={`setup-character-${index}-name`}
                  name={formFieldName(draft.playerId, 'characterName')}
                  value={draft.characterName}
                  onChange={(event) => updateDraft(index, { characterName: event.target.value })}
                  autoComplete="off"
                  required={draft.status !== 'confirmed'}
                />

                <label htmlFor={`setup-character-${index}-template`}>Character template</label>
                <select
                  id={`setup-character-${index}-template`}
                  name={formFieldName(draft.playerId, 'templateId')}
                  value={draft.templateId}
                  onChange={(event) => updateDraft(index, {
                    templateId: event.target.value,
                    mode: 'template',
                    importPayload: null,
                    importFileName: '',
                    importError: '',
                  })}
                >
                  {CHARACTER_TEMPLATE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </select>
                {draft.mode === 'template' && <p className="character-template-summary">{selectedTemplate?.summary}</p>}

                <div className="character-file-field">
                  <label htmlFor={`setup-character-${index}-file`}>Import local JSON for Player {index + 1}</label>
                  <input
                    id={`setup-character-${index}-file`}
                    type="file"
                    accept="application/json,.json"
                    onChange={(event) => handleImport(index, event.target.files?.[0])}
                  />
                </div>
                {draft.importError && <p className="character-field-error" role="alert">{draft.importError}</p>}
                {draft.mode === 'import' && (
                  <div className="character-import-status" role="status">
                    Using local file <strong>{draft.importFileName}</strong>. The game server will validate it.
                    <button type="button" onClick={() => updateDraft(index, {
                      mode: 'template', importPayload: null, importFileName: '', importError: '',
                    })}>Use template instead</button>
                  </div>
                )}
                {draft.status !== 'empty' && <p className="character-seat-status">Server status: {draft.status}</p>}
              </fieldset>
            );
          })}
        </div>

        {error && <p className="character-setup-error" role="alert">{error.message}</p>}
        {progress && (
          <p className="character-setup-progress" role="status" aria-live="polite">
            {progress.label} · {progress.completed}/{progress.total}
          </p>
        )}

        <button className="character-setup-submit" type="submit" disabled={submitting || complete}>
          {complete ? 'Characters confirmed' : submitting ? 'Preparing characters…' : 'Stage and confirm both characters'}
        </button>
      </form>
    </section>
  );
}
