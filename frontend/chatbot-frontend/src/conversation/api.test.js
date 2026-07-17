import {
  ConversationApiError,
  clearConversation,
  readConversation,
  writeConversationMessage,
} from './api';

function response(payload, { ok = true, status = 200 } = {}) {
  return {
    ok,
    status,
    json: jest.fn(async () => payload),
  };
}

describe('conversation persistence API', () => {
  test('reads, upserts, and clears a session Chronicle', async () => {
    const fetchImpl = jest
      .fn()
      .mockResolvedValueOnce(response({
        session_id: 'one-shot-1',
        messages: [{
          message_id: 'user:turn-1',
          role: 'user',
          text: 'I inspect the seal.',
          created_at: '2026-07-09T12:00:00Z',
        }],
      }))
      .mockResolvedValueOnce(response({ ok: true }))
      .mockResolvedValueOnce(response({ ok: true }));

    const restored = await readConversation({
      sessionId: 'one-shot-1',
      apiBaseUrl: 'http://dm.test/',
      fetchImpl,
    });
    await writeConversationMessage({
      sessionId: 'one-shot-1',
      messageId: 'assistant:turn/2',
      role: 'assistant',
      text: 'The wax is recently disturbed.',
      apiBaseUrl: 'http://dm.test',
      fetchImpl,
    });
    await clearConversation({
      sessionId: 'one-shot-1',
      apiBaseUrl: 'http://dm.test',
      fetchImpl,
    });

    expect(restored.messages).toHaveLength(1);
    expect(fetchImpl).toHaveBeenNthCalledWith(
      1,
      'http://dm.test/api/sessions/one-shot-1/conversation',
      { headers: { Accept: 'application/json' } },
    );
    expect(fetchImpl).toHaveBeenNthCalledWith(
      2,
      'http://dm.test/api/sessions/one-shot-1/conversation/messages/assistant%3Aturn%2F2',
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({
          role: 'assistant',
          text: 'The wax is recently disturbed.',
        }),
      }),
    );
    expect(fetchImpl).toHaveBeenNthCalledWith(
      3,
      'http://dm.test/api/sessions/one-shot-1/conversation',
      expect.objectContaining({ method: 'DELETE' }),
    );
  });

  test('preserves status while sanitizing an API failure', async () => {
    const fetchImpl = jest.fn(async () => response(
      { error: { message: 'That session does not exist.' } },
      { ok: false, status: 404 },
    ));

    await expect(readConversation({
      sessionId: 'missing',
      fetchImpl,
    })).rejects.toEqual(expect.objectContaining({
      name: 'ConversationApiError',
      status: 404,
      message: 'That session does not exist.',
    }));
    await expect(readConversation({ sessionId: 'missing', fetchImpl }))
      .rejects.toBeInstanceOf(ConversationApiError);
  });
});
