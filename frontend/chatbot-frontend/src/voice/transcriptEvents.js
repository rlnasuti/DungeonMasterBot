function eventDescriptor(event) {
  switch (event?.type) {
    case 'conversation.item.input_audio_transcription.delta':
      return {
        id: `user:${event.item_id || 'current'}`,
        role: 'user',
        text: event.delta,
        final: false,
        replace: false,
      };
    case 'conversation.item.input_audio_transcription.completed':
      return {
        id: `user:${event.item_id || 'current'}`,
        role: 'user',
        text: event.transcript,
        final: true,
        replace: true,
      };
    case 'response.output_audio_transcript.delta':
      return {
        id: `assistant:${event.item_id || event.response_id || 'current'}`,
        role: 'assistant',
        text: event.delta,
        final: false,
        replace: false,
      };
    case 'response.output_audio_transcript.done':
      return {
        id: `assistant:${event.item_id || event.response_id || 'current'}`,
        role: 'assistant',
        text: event.transcript,
        final: true,
        replace: true,
      };
    case 'response.output_text.delta':
      return {
        id: `assistant:${event.item_id || event.response_id || 'current'}:text`,
        role: 'assistant',
        text: event.delta,
        final: false,
        replace: false,
      };
    case 'response.output_text.done':
      return {
        id: `assistant:${event.item_id || event.response_id || 'current'}:text`,
        role: 'assistant',
        text: event.text,
        final: true,
        replace: true,
      };
    default:
      return null;
  }
}

/** Pure reducer for the subset of Realtime server events that carry text. */
export function reduceTranscriptEvent(messages, event) {
  const descriptor = eventDescriptor(event);
  if (!descriptor || typeof descriptor.text !== 'string') return messages;

  const index = messages.findIndex((message) => message.id === descriptor.id);
  if (index === -1) {
    if (!descriptor.text && !descriptor.final) return messages;
    return [
      ...messages,
      {
        id: descriptor.id,
        role: descriptor.role,
        text: descriptor.text,
        final: descriptor.final,
      },
    ];
  }

  const current = messages[index];
  const nextMessage = {
    ...current,
    text: descriptor.replace
      ? descriptor.text
      : `${current.text}${descriptor.text}`,
    final: descriptor.final,
  };
  return [
    ...messages.slice(0, index),
    nextMessage,
    ...messages.slice(index + 1),
  ];
}

export function isAssistantSpeechEvent(event) {
  return (
    event?.type === 'response.output_audio_transcript.delta' ||
    event?.type === 'response.output_text.delta' ||
    event?.type === 'response.output_audio.delta'
  );
}

export function isAssistantSpeechDoneEvent(event) {
  return (
    event?.type === 'response.done' ||
    event?.type === 'response.output_audio.done'
  );
}
