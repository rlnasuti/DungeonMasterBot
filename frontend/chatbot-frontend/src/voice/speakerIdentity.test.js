import {
  decodePersistedSpeakerText,
  encodePersistedSpeakerText,
  microphoneMutedControlEvent,
  rememberTurnSpeaker,
  speakerForTranscriptEntry,
  speakerOptionsFromPlayers,
  speakerSelectionControlEvent,
  speakerTurnControlEvent,
} from './speakerIdentity';

const cendien = {
  playerId: 'player-one',
  characterName: 'Cendien',
  displayName: 'Robert',
  label: 'Cendien',
};

test('derives microphone labels from confirmed character names with seat fallbacks', () => {
  expect(speakerOptionsFromPlayers([
    {
      player_id: 'player-one',
      display_name: 'Robert',
      character_status: 'confirmed',
      character: { name: 'Cendien' },
    },
    {
      player_id: 'player-two',
      display_name: 'Player Two',
      character_status: 'empty',
    },
  ])).toEqual([
    cendien,
    {
      playerId: 'player-two',
      characterName: null,
      displayName: 'Player Two',
      label: 'Player Two',
    },
  ]);
});

test('builds bounded app-owned identity controls around the committed audio item', () => {
  const selection = speakerSelectionControlEvent(cendien);
  expect(selection).toMatchObject({
    type: 'conversation.item.create',
    item: {
      type: 'message',
      role: 'system',
      content: [{ type: 'input_text' }],
    },
  });
  expect(selection.item.content[0].text).toContain('APP-OWNED SPEAKER SELECTION');
  expect(selection.item.content[0].text).toContain('"character_name":"Cendien"');

  const turn = speakerTurnControlEvent(cendien, 'audio-item-7');
  expect(turn.previous_item_id).toBe('audio-item-7');
  expect(turn.item.content[0].text).toContain('APP-OWNED SPEAKER TURN');
  expect(turn.item.content[0].text).toContain('"audio_item_id":"audio-item-7"');

  expect(microphoneMutedControlEvent().item.content[0].text).toContain('microphone is muted');
});

test('maps a server audio item to its local transcript and preserves the label across persistence', () => {
  const turns = new Map();
  expect(rememberTurnSpeaker(turns, 'audio-item-7', cendien)).toBe(true);
  expect(speakerForTranscriptEntry({
    id: 'user:audio-item-7',
    role: 'user',
  }, turns)).toEqual(cendien);

  const encoded = encodePersistedSpeakerText('I inspect the stair.', cendien);
  expect(encoded).toContain('[[DMB-SPEAKER:player-one:Cendien]]');
  expect(decodePersistedSpeakerText(encoded)).toEqual({
    text: 'I inspect the stair.',
    speaker: {
      playerId: 'player-one',
      characterName: 'Cendien',
      displayName: null,
      label: 'Cendien',
    },
  });
});
