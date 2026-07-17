import React from 'react';
import './DungeonMasterPortrait.css';

const PORTRAIT_SRC = '/assets/dungeon-master-portrait-marin.png';

const STATUS_LABELS = {
  idle: 'Ready when you are',
  connecting: 'Opening the story circle…',
  listening: 'Listening to the party',
  speaking: 'Narrating',
  muted: 'Microphone muted',
  error: 'Voice connection needs attention',
};

function normalizedAudioLevel(value) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return 0;
  return Math.min(1, Math.max(0, parsed));
}

export default function DungeonMasterPortrait({
  state = 'idle',
  audioLevel = 0,
  name = 'Marin',
}) {
  const level = normalizedAudioLevel(audioLevel);
  const status = STATUS_LABELS[state] ?? STATUS_LABELS.idle;

  return (
    <section
      className={`dm-presence dm-presence--${state}`}
      aria-label={`${name} voice status`}
      style={{
        '--speech-level': level,
        '--mouth-x': '49.5%',
        '--mouth-y': '47.2%',
        '--mouth-width': '11.2%',
        '--mouth-height': '2.7%',
      }}
    >
      <div className="dm-portrait-shell" aria-hidden="true">
        <span className="dm-aura dm-aura--outer" />
        <span className="dm-aura dm-aura--inner" />
        <div className="dm-art-stack">
          <img className="dm-portrait-image" src={PORTRAIT_SRC} alt="" />
          <span className="dm-mouth-opening" />
          <span className="dm-listening-ring" />
        </div>
      </div>

      <div className="dm-presence-copy">
        <p className="dm-presence-kicker">At the head of the table</p>
        <h2>{name}</h2>
        <div className="dm-voice-status" role="status" aria-live="polite">
          <span className="dm-status-dot" aria-hidden="true" />
          <span>{status}</span>
          {state === 'speaking' && (
            <span className="dm-speech-meter" aria-hidden="true">
              <i />
              <i />
              <i />
              <i />
            </span>
          )}
        </div>
      </div>
    </section>
  );
}
