import React from 'react';
import { VOICE_STATES, useVoiceDungeonMaster } from './useVoiceDungeonMaster';

/**
 * Headless-friendly voice controller. Pass a function as `children` or
 * `render` to own the UI, or use the small accessible default controls.
 */
export function VoiceDungeonMaster({ children, render, ...voiceOptions }) {
  const voice = useVoiceDungeonMaster(voiceOptions);
  const renderVoice = typeof children === 'function' ? children : render;

  if (typeof renderVoice === 'function') return renderVoice(voice);

  const canConnect =
    voice.status === VOICE_STATES.IDLE || voice.status === VOICE_STATES.ERROR;
  const connecting = voice.status === VOICE_STATES.CONNECTING;
  const showConnect = canConnect || connecting;

  return (
    <section aria-label="Voice dungeon master">
      <p aria-live="polite">Voice status: {voice.status}</p>
      {voice.error && <p role="alert">{voice.error.message}</p>}
      {showConnect ? (
        <button type="button" onClick={voice.connect} disabled={connecting}>
          {connecting ? 'Connecting…' : 'Start voice session'}
        </button>
      ) : (
        <>
          <button type="button" onClick={voice.toggleMuted}>
            {voice.muted ? 'Unmute microphone' : 'Mute microphone'}
          </button>
          <button type="button" onClick={voice.disconnect}>
            Disconnect voice session
          </button>
        </>
      )}
    </section>
  );
}

export default VoiceDungeonMaster;
