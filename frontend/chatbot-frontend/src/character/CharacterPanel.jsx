import React, { useEffect, useMemo, useState } from 'react';
import { createGameApi } from './api';
import CharacterSheet from './CharacterSheet';
import { normalizePendingRolls, normalizePlayers } from './normalize';
import { useGameState } from './useGameState';
import './character.css';

export default function CharacterPanel({
  sessionId,
  api: suppliedApi,
  apiBaseUrl = 'http://localhost:8000',
  pollIntervalMs = 3000,
  className = '',
}) {
  const api = useMemo(
    () => suppliedApi || createGameApi(apiBaseUrl),
    [apiBaseUrl, suppliedApi],
  );
  const {
    snapshot,
    loading,
    error,
    submittingRollId,
    refresh,
    submitPhysicalRoll,
  } = useGameState({ sessionId, api, pollIntervalMs });
  const players = useMemo(() => normalizePlayers(snapshot), [snapshot]);
  const pendingRolls = useMemo(() => normalizePendingRolls(snapshot), [snapshot]);
  const [selectedPlayerId, setSelectedPlayerId] = useState(null);

  const selectAndFocusPlayer = (player) => {
    setSelectedPlayerId(player.playerId);
    window.requestAnimationFrame(() => {
      document.getElementById(`character-tab-${player.playerId}`)?.focus();
    });
  };

  const handleTabKeyDown = (event, currentIndex) => {
    let nextIndex = null;
    if (event.key === 'ArrowRight') nextIndex = (currentIndex + 1) % players.length;
    if (event.key === 'ArrowLeft') nextIndex = (currentIndex - 1 + players.length) % players.length;
    if (event.key === 'Home') nextIndex = 0;
    if (event.key === 'End') nextIndex = players.length - 1;
    if (nextIndex === null) return;
    event.preventDefault();
    selectAndFocusPlayer(players[nextIndex]);
  };

  useEffect(() => {
    setSelectedPlayerId((currentPlayerId) => {
      if (!players.length) return null;
      if (players.some((player) => player.playerId === currentPlayerId)) return currentPlayerId;
      return players[0].playerId;
    });
  }, [players]);

  if (!sessionId) {
    return (
      <section className={`character-panel character-panel-state ${className}`} aria-label="Character sheets">
        <h2>Character sheets</h2>
        <p>No game session selected.</p>
      </section>
    );
  }

  if (loading && !snapshot) {
    return (
      <section
        className={`character-panel character-panel-state ${className}`}
        aria-label="Character sheets"
        aria-busy="true"
      >
        <p role="status">Loading character sheets…</p>
      </section>
    );
  }

  if (error && !snapshot) {
    return (
      <section className={`character-panel character-panel-state ${className}`} aria-label="Character sheets">
        <div role="alert">
          <h2>Character sheets unavailable</h2>
          <p>{error.message || 'The game state could not be loaded.'}</p>
        </div>
        <button type="button" onClick={() => refresh({ initial: true })}>Try again</button>
      </section>
    );
  }

  if (!players.length) {
    return (
      <section className={`character-panel character-panel-state ${className}`} aria-label="Character sheets">
        <h2>Character sheets</h2>
        <p>No player characters have joined this session yet.</p>
        <button type="button" onClick={() => refresh()}>Refresh</button>
      </section>
    );
  }

  const selectedPlayer = players.find((player) => player.playerId === selectedPlayerId) || players[0];
  const selectedRoll = pendingRolls.find((roll) => (
    !roll.playerId || roll.playerId === selectedPlayer.playerId
  ));

  return (
    <section className={`character-panel ${className}`} aria-label="Character sheets">
      <header className="character-panel-toolbar">
        <div>
          <p className="character-eyebrow">Live party state</p>
          <h1>Character sheets</h1>
        </div>
        <div className="character-sync-status">
          <span>State v{snapshot?.state_version ?? '—'}</span>
          <button type="button" onClick={() => refresh()} aria-label="Refresh character sheets">
            Refresh
          </button>
        </div>
      </header>

      {error && (
        <div className="character-sync-error" role="alert">
          Showing the last known state. Refresh failed: {error.message}
        </div>
      )}

      <div className="character-tabs" role="tablist" aria-label="Players">
        {players.map((player, index) => {
          const isSelected = player.playerId === selectedPlayer.playerId;
          const hasPendingRoll = pendingRolls.some((roll) => (
            !roll.playerId || roll.playerId === player.playerId
          ));
          return (
            <button
              key={player.playerId}
              id={`character-tab-${player.playerId}`}
              type="button"
              role="tab"
              aria-selected={isSelected}
              aria-controls={`character-panel-${player.playerId}`}
              tabIndex={isSelected ? 0 : -1}
              onClick={() => setSelectedPlayerId(player.playerId)}
              onKeyDown={(event) => handleTabKeyDown(event, index)}
            >
              <span>{player.playerLabel}</span>
              <small>{player.characterName}</small>
              {hasPendingRoll && <i className="character-roll-dot" aria-label="Roll waiting" />}
            </button>
          );
        })}
      </div>

      <div
        id={`character-panel-${selectedPlayer.playerId}`}
        role="tabpanel"
        aria-labelledby={`character-tab-${selectedPlayer.playerId}`}
        tabIndex="0"
      >
        <CharacterSheet
          player={selectedPlayer}
          pendingRoll={selectedRoll}
          submittingRollId={submittingRollId}
          onSubmitRoll={submitPhysicalRoll}
        />
      </div>
    </section>
  );
}
