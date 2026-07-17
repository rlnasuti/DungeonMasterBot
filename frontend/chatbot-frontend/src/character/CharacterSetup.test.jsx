import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { CharacterSetup } from './index';

const sessionSnapshot = {
  session_id: 'session-setup',
  state_version: 10,
  players: [
    { player_id: 'player-one', display_name: 'Player One', character_status: 'empty' },
    { player_id: 'player-two', display_name: 'Player Two', character_status: 'empty' },
  ],
};

function createApi() {
  return {
    getGameState: jest.fn().mockResolvedValue(sessionSnapshot),
    updatePlayerIdentity: jest.fn(),
    stageCharacter: jest.fn()
      .mockResolvedValueOnce({ state_version: 11 })
      .mockResolvedValueOnce({ state_version: 13 }),
    confirmCharacter: jest.fn()
      .mockResolvedValueOnce({ state_version: 12 })
      .mockResolvedValueOnce({ state_version: 14 }),
  };
}

async function renderSetup(api = createApi(), onComplete = jest.fn()) {
  render(
    <CharacterSetup
      sessionId="session-setup"
      api={api}
      onComplete={onComplete}
    />,
  );
  await screen.findByRole('heading', { name: /Ready your adventurers/i });
  return { api, onComplete };
}

function nameBothCharacters(first = 'Aster', second = 'Bram') {
  const characterNames = screen.getAllByLabelText('Character name');
  fireEvent.change(characterNames[0], { target: { value: first } });
  fireEvent.change(characterNames[1], { target: { value: second } });
}

test('stages and confirms two templates in state-version order', async () => {
  const { api, onComplete } = await renderSetup();
  nameBothCharacters();

  fireEvent.click(screen.getByRole('button', { name: /Stage and confirm both characters/i }));

  await waitFor(() => expect(onComplete).toHaveBeenCalledTimes(1));
  expect(api.stageCharacter).toHaveBeenNthCalledWith(
    1,
    'session-setup',
    'player-one',
    expect.objectContaining({
      source: 'created',
      expected_state_version: 10,
      idempotency_key: expect.stringContaining('player-one:stage'),
      character: expect.objectContaining({ name: 'Aster', class_name: 'Fighter', level: 3 }),
    }),
  );
  expect(api.confirmCharacter).toHaveBeenNthCalledWith(
    1,
    'session-setup',
    'player-one',
    expect.objectContaining({
      expected_state_version: 11,
      idempotency_key: expect.stringContaining('player-one:confirm'),
    }),
  );
  expect(api.stageCharacter).toHaveBeenNthCalledWith(
    2,
    'session-setup',
    'player-two',
    expect.objectContaining({
      source: 'created',
      expected_state_version: 12,
      character: expect.objectContaining({ name: 'Bram', class_name: 'Wizard', level: 3 }),
    }),
  );
  expect(api.confirmCharacter).toHaveBeenNthCalledWith(
    2,
    'session-setup',
    'player-two',
    expect.objectContaining({ expected_state_version: 13 }),
  );
  const fighter = api.stageCharacter.mock.calls[0][2].character;
  expect(fighter).toEqual(expect.objectContaining({
    ruleset_id: 'srd-5.2.1',
    subclass_name: 'Champion',
    armor_class: 19,
  }));
  expect(fighter.armor_class_calculation.source_item_ids).toHaveLength(2);
  expect(fighter.inventory.map((entry) => entry.name)).toEqual(
    expect.arrayContaining(['Chain Mail', 'Shield', 'Longsword']),
  );
  expect(fighter.class_resources.second_wind).toEqual({ maximum: 2, current: 2 });
  expect(fighter.attacks).toEqual(expect.arrayContaining([
    expect.objectContaining({ name: 'Longsword', attack_bonus: 5 }),
  ]));

  const wizard = api.stageCharacter.mock.calls[1][2].character;
  expect(wizard).toEqual(expect.objectContaining({
    ruleset_id: 'srd-5.2.1',
    subclass_name: 'Evoker',
    armor_class: 12,
  }));
  expect(wizard.spellcasting.spellbook_spell_ids).toHaveLength(12);
  expect(wizard.spellcasting.prepared_spell_ids).toHaveLength(6);
  expect(wizard.spellcasting.always_prepared_spell_ids).toEqual(
    expect.arrayContaining(['detect-magic', 'longstrider']),
  );
  expect(wizard.spellcasting.spells).toEqual(expect.arrayContaining([
    expect.objectContaining({ name: 'Sleep', concentration: true, range: '60 feet' }),
  ]));
  expect(onComplete).toHaveBeenCalledWith(expect.objectContaining({
    session_id: 'session-setup',
    state_version: 14,
    players: [
      expect.objectContaining({ display_name: 'Player One', character_name: 'Aster' }),
      expect.objectContaining({ display_name: 'Player Two', character_name: 'Bram' }),
    ],
  }));
  expect(api.updatePlayerIdentity).not.toHaveBeenCalled();
  expect(screen.getByRole('button', { name: 'Characters confirmed' })).toBeDisabled();
});

test('commits the exact Player 1 Wizard and Player 2 Fighter selections shown by the form', async () => {
  const { api, onComplete } = await renderSetup();
  nameBothCharacters('Bobbarino', 'Bram');
  const templates = screen.getAllByLabelText('Character template');

  // A native select can update its committed DOM value before React has
  // delivered the corresponding change callback. Submission must treat the
  // form controls—not an earlier component-state snapshot—as authoritative.
  const setNativeValue = Object.getOwnPropertyDescriptor(
    window.HTMLSelectElement.prototype,
    'value',
  ).set;
  setNativeValue.call(templates[0], 'wizard');
  setNativeValue.call(templates[1], 'fighter');

  fireEvent.submit(screen.getByRole('button', { name: /Stage and confirm both characters/i }).closest('form'));

  await waitFor(() => expect(onComplete).toHaveBeenCalledTimes(1));
  expect(api.stageCharacter).toHaveBeenNthCalledWith(
    1,
    'session-setup',
    'player-one',
    expect.objectContaining({
      character: expect.objectContaining({
        name: 'Bobbarino',
        class_name: 'Wizard',
        character_id: 'character-player-one-wizard',
      }),
    }),
  );
  expect(api.stageCharacter).toHaveBeenNthCalledWith(
    2,
    'session-setup',
    'player-two',
    expect.objectContaining({
      character: expect.objectContaining({
        name: 'Bram',
        class_name: 'Fighter',
        character_id: 'character-player-two-fighter',
      }),
    }),
  );
});

test('persists edited display names in the same state-version sequence', async () => {
  const api = createApi();
  api.updatePlayerIdentity
    .mockResolvedValueOnce({ state_version: 11 })
    .mockResolvedValueOnce({ state_version: 14 });
  api.stageCharacter
    .mockReset()
    .mockResolvedValueOnce({ state_version: 12 })
    .mockResolvedValueOnce({ state_version: 15 });
  api.confirmCharacter
    .mockReset()
    .mockResolvedValueOnce({ state_version: 13 })
    .mockResolvedValueOnce({ state_version: 16 });
  const { onComplete } = await renderSetup(api);
  const displayNames = screen.getAllByLabelText('Player display name');
  fireEvent.change(displayNames[0], { target: { value: 'Robert' } });
  fireEvent.change(displayNames[1], { target: { value: 'Juice' } });
  nameBothCharacters('Cendien', 'Juicebox');

  fireEvent.click(screen.getByRole('button', { name: /Stage and confirm both characters/i }));

  await waitFor(() => expect(onComplete).toHaveBeenCalledTimes(1));
  expect(api.updatePlayerIdentity).toHaveBeenNthCalledWith(
    1,
    'session-setup',
    'player-one',
    {
      display_name: 'Robert',
      expected_state_version: 10,
      idempotency_key: expect.stringContaining('player-one:identity'),
    },
  );
  expect(api.stageCharacter.mock.calls[0][2].expected_state_version).toBe(11);
  expect(api.confirmCharacter.mock.calls[0][2].expected_state_version).toBe(12);
  expect(api.updatePlayerIdentity).toHaveBeenNthCalledWith(
    2,
    'session-setup',
    'player-two',
    {
      display_name: 'Juice',
      expected_state_version: 13,
      idempotency_key: expect.stringContaining('player-two:identity'),
    },
  );
  expect(api.stageCharacter.mock.calls[1][2].expected_state_version).toBe(14);
  expect(api.confirmCharacter.mock.calls[1][2].expected_state_version).toBe(15);
  expect(onComplete).toHaveBeenCalledWith(expect.objectContaining({
    state_version: 16,
    players: [
      expect.objectContaining({ display_name: 'Robert', character_name: 'Cendien' }),
      expect.objectContaining({ display_name: 'Juice', character_name: 'Juicebox' }),
    ],
  }));
});

test('updates a confirmed player display name without renaming the character', async () => {
  const confirmedSnapshot = {
    ...sessionSnapshot,
    players: [
      {
        player_id: 'player-one',
        display_name: 'Player One',
        character_status: 'confirmed',
        character: { name: 'Cendien', class_name: 'Wizard' },
      },
      {
        player_id: 'player-two',
        display_name: 'Player Two',
        character_status: 'confirmed',
        character: { name: 'Juicebox', class_name: 'Fighter' },
      },
    ],
  };
  const api = createApi();
  api.getGameState.mockResolvedValue(confirmedSnapshot);
  api.updatePlayerIdentity.mockResolvedValue({ state_version: 11 });
  const { onComplete } = await renderSetup(api);
  fireEvent.change(screen.getAllByLabelText('Player display name')[0], {
    target: { value: 'Robert' },
  });
  fireEvent.change(screen.getAllByLabelText('Character name')[0], {
    target: { value: 'This must not be sent' },
  });

  fireEvent.click(screen.getByRole('button', { name: /Stage and confirm both characters/i }));

  await waitFor(() => expect(onComplete).toHaveBeenCalledTimes(1));
  expect(api.updatePlayerIdentity).toHaveBeenCalledWith(
    'session-setup',
    'player-one',
    {
      display_name: 'Robert',
      expected_state_version: 10,
      idempotency_key: expect.stringContaining('player-one:identity'),
    },
  );
  expect(api.updatePlayerIdentity.mock.calls[0][2]).not.toHaveProperty('character_name');
  expect(api.stageCharacter).not.toHaveBeenCalled();
  expect(api.confirmCharacter).not.toHaveBeenCalled();
});

test('imports local JSON without sending private or hidden fields', async () => {
  const { api, onComplete } = await renderSetup();
  expect(screen.getByText(/does not connect to or automate D&D Beyond/i)).toBeInTheDocument();

  const importedCharacter = {
    character: {
      character_id: 'imported-character',
      name: 'Cinder',
      class_name: 'Wizard',
      level: 3,
      ancestry: 'Human',
      background: 'Sage',
      hp: 18,
      max_hp: 18,
      temp_hp: 0,
      armor_class: 13,
      proficiency_bonus: 2,
      abilities: {
        strength: 8, dexterity: 14, constitution: 12,
        intelligence: 16, wisdom: 13, charisma: 10,
        secret_score: 99,
      },
      saving_throws: {
        strength: -1, dexterity: 2, constitution: 1,
        intelligence: 5, wisdom: 3, charisma: 0,
      },
      skills: { arcana: 5 },
      hit_dice: { d6: { maximum: 3, current: 3 } },
      spell_slots: { 1: { maximum: 4, current: 4 } },
      class_resources: {
        arcane_recovery: { maximum: 1, current: 1 },
        secret_meter: { maximum: 9, current: 9 },
      },
      conditions: ['Blessed', { hidden: 'do not send' }],
      inventory: [{
        item_id: 'spellbook', name: 'Spellbook', quantity: 1, equipped: true,
        notes: '', dm_notes: 'private campaign clue',
      }],
      private_world: { secret: 'do not send' },
      secrets: ['do not send'],
    },
    private_world: { motives: ['do not send'] },
  };
  const file = new File(
    [JSON.stringify(importedCharacter)],
    'cinder.json',
    { type: 'application/json' },
  );
  fireEvent.change(screen.getByLabelText('Import local JSON for Player 1'), {
    target: { files: [file] },
  });
  await screen.findByText(/Using local file/i);
  fireEvent.change(screen.getAllByLabelText('Character name')[1], { target: { value: 'Bram' } });

  fireEvent.click(screen.getByRole('button', { name: /Stage and confirm both characters/i }));
  await waitFor(() => expect(onComplete).toHaveBeenCalledTimes(1));

  const submission = api.stageCharacter.mock.calls[0][2];
  expect(submission.source).toBe('imported');
  expect(submission.character.name).toBe('Cinder');
  expect(submission.character).not.toHaveProperty('private_world');
  expect(submission.character).not.toHaveProperty('secrets');
  expect(submission.character.abilities).not.toHaveProperty('secret_score');
  expect(submission.character.class_resources).not.toHaveProperty('secret_meter');
  expect(submission.character.conditions).toEqual(['Blessed']);
  expect(submission.character.inventory[0]).not.toHaveProperty('dm_notes');
});

test('surfaces server validation and reuses the in-flight idempotency key', async () => {
  const api = createApi();
  api.stageCharacter = jest.fn()
    .mockRejectedValueOnce(new Error('Server rejected the character payload.'))
    .mockResolvedValueOnce({ state_version: 11 })
    .mockResolvedValueOnce({ state_version: 13 });
  const { onComplete } = await renderSetup(api);
  nameBothCharacters();

  fireEvent.click(screen.getByRole('button', { name: /Stage and confirm both characters/i }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Server rejected the character payload.');
  const firstKey = api.stageCharacter.mock.calls[0][2].idempotency_key;

  fireEvent.click(screen.getByRole('button', { name: /Stage and confirm both characters/i }));
  await waitFor(() => expect(onComplete).toHaveBeenCalledTimes(1));
  expect(api.stageCharacter.mock.calls[1][2].idempotency_key).toBe(firstKey);
});
