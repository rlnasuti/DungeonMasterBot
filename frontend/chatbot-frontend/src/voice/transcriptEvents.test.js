import {
  isAssistantSpeechDoneEvent,
  isAssistantSpeechEvent,
  reduceTranscriptEvent,
} from './transcriptEvents';

describe('Realtime transcript event reducer', () => {
  test('accumulates and finalizes player speech', () => {
    let transcript = [];
    transcript = reduceTranscriptEvent(transcript, {
      type: 'conversation.item.input_audio_transcription.delta',
      item_id: 'player-turn-1',
      delta: 'I inspect ',
    });
    transcript = reduceTranscriptEvent(transcript, {
      type: 'conversation.item.input_audio_transcription.delta',
      item_id: 'player-turn-1',
      delta: 'the door.',
    });
    transcript = reduceTranscriptEvent(transcript, {
      type: 'conversation.item.input_audio_transcription.completed',
      item_id: 'player-turn-1',
      transcript: 'I inspect the door.',
    });

    expect(transcript).toEqual([
      {
        id: 'user:player-turn-1',
        role: 'user',
        text: 'I inspect the door.',
        final: true,
      },
    ]);
  });

  test('keeps assistant turns distinct and ignores unrelated events', () => {
    const initial = [];
    expect(
      reduceTranscriptEvent(initial, { type: 'session.updated' }),
    ).toBe(initial);

    let transcript = reduceTranscriptEvent(initial, {
      type: 'response.output_audio_transcript.delta',
      item_id: 'dm-turn-1',
      delta: 'The hinges ',
    });
    transcript = reduceTranscriptEvent(transcript, {
      type: 'response.output_audio_transcript.done',
      item_id: 'dm-turn-1',
      transcript: 'The hinges are freshly oiled.',
    });

    expect(transcript[0]).toMatchObject({
      role: 'assistant',
      text: 'The hinges are freshly oiled.',
      final: true,
    });
  });

  test('classifies speaking lifecycle events', () => {
    expect(
      isAssistantSpeechEvent({ type: 'response.output_audio.delta' }),
    ).toBe(true);
    expect(isAssistantSpeechDoneEvent({ type: 'response.done' })).toBe(true);
    expect(isAssistantSpeechEvent({ type: 'response.created' })).toBe(false);
  });
});
