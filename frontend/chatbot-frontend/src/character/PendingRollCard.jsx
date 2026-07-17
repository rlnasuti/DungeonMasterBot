import React, { useState } from 'react';
import { formatModifier } from './normalize';

function dieMaximum(die) {
  const match = /^d(\d+)$/i.exec(die);
  return match ? Number(match[1]) : 20;
}

export default function PendingRollCard({ roll, player, submitting, onSubmit }) {
  const [naturalRoll, setNaturalRoll] = useState('');
  const [validationError, setValidationError] = useState('');
  const maximum = dieMaximum(roll.die);

  const handleSubmit = async (event) => {
    event.preventDefault();
    const value = Number(naturalRoll);
    if (!Number.isInteger(value) || value < 1 || value > maximum) {
      setValidationError(`Enter the face shown on the ${roll.die}: 1 through ${maximum}.`);
      return;
    }

    setValidationError('');
    const accepted = await onSubmit({
      rollId: roll.id,
      playerId: player.playerId,
      naturalRoll: value,
    });
    if (accepted) setNaturalRoll('');
  };

  return (
    <aside className="character-roll-card" aria-labelledby={`roll-${roll.id}-title`}>
      <div>
        <p className="character-eyebrow">Physical roll needed</p>
        <h3 id={`roll-${roll.id}-title`}>{roll.label}</h3>
        <p>
          Roll a <strong>{roll.die}</strong>
          {roll.modifier !== undefined && roll.modifier !== null
            ? `. The game will apply ${formatModifier(roll.modifier)}`
            : ''}.
          {roll.advantage !== 'normal' ? ` Roll with ${roll.advantage}.` : ''}
        </p>
        {roll.targetTotal !== null && roll.targetTotal !== undefined && (
          <p className="character-roll-target">Target {roll.targetTotal}</p>
        )}
      </div>
      <form onSubmit={handleSubmit} noValidate>
        <label htmlFor={`roll-${roll.id}-value`}>Physical {roll.die} result</label>
        <div className="character-roll-entry">
          <input
            id={`roll-${roll.id}-value`}
            type="number"
            inputMode="numeric"
            min="1"
            max={maximum}
            value={naturalRoll}
            onChange={(event) => setNaturalRoll(event.target.value)}
            disabled={submitting}
            required
          />
          <button type="submit" disabled={submitting || naturalRoll === ''}>
            {submitting ? 'Submitting…' : 'Submit roll'}
          </button>
        </div>
        {validationError && <p className="character-field-error" role="alert">{validationError}</p>}
      </form>
    </aside>
  );
}
