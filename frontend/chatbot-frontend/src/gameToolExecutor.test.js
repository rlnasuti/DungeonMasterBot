import { createGameToolExecutor } from './gameToolExecutor';

function response(payload, { ok = true, status = 200 } = {}) {
  return { ok, status, json: jest.fn(async () => payload) };
}

describe('game tool executor', () => {
  test('adds authoritative version and idempotency to a physical-roll request', async () => {
    const fetchImpl = jest.fn()
      .mockResolvedValueOnce(response({ state_version: 7, players: [] }))
      .mockResolvedValueOnce(response({ state_version: 8, pending_roll: { roll_id: 'roll-1' } }));
    const execute = createGameToolExecutor({ sessionId: 'session 1', fetchImpl });

    const result = await execute({
      name: 'request_physical_roll',
      callId: 'call-1',
      arguments: {
        player_id: 'player-1',
        roll_kind: 'skill',
        check_key: 'perception',
        difficulty: 'medium',
        dc_visibility: 'private',
        prompt: 'Roll Perception.',
      },
    });

    expect(result.ok).toBe(true);
    expect(fetchImpl.mock.calls[0][0]).toContain('/api/sessions/session%201/view');
    expect(fetchImpl.mock.calls[1][0]).toContain('/director/roll');
    const mutation = JSON.parse(fetchImpl.mock.calls[1][1].body);
    expect(mutation).toEqual(expect.objectContaining({
      difficulty: 'medium',
      dc_visibility: 'private',
      expected_state_version: 7,
      idempotency_key: 'voice:call-1:request_physical_roll',
    }));
    expect(mutation).not.toHaveProperty('dc');
    expect(mutation).not.toHaveProperty('engine_modifier');
  });

  test('serializes state-changing calls so each reads a fresh version', async () => {
    const fetchImpl = jest.fn()
      .mockResolvedValueOnce(response({ state_version: 2 }))
      .mockResolvedValueOnce(response({ state_version: 3 }))
      .mockResolvedValueOnce(response({ state_version: 3 }))
      .mockResolvedValueOnce(response({ state_version: 4 }));
    const execute = createGameToolExecutor({ sessionId: 'game', fetchImpl });

    await Promise.all([
      execute({ name: 'apply_damage', callId: 'a', arguments: { player_id: 'p1', amount: 2 } }),
      execute({ name: 'apply_healing', callId: 'b', arguments: { player_id: 'p1', amount: 1 } }),
    ]);

    expect(JSON.parse(fetchImpl.mock.calls[1][1].body).expected_state_version).toBe(2);
    expect(JSON.parse(fetchImpl.mock.calls[3][1].body).expected_state_version).toBe(3);
  });

  test('rejects names outside the fixed game-tool vocabulary without a request', async () => {
    const fetchImpl = jest.fn();
    const execute = createGameToolExecutor({ sessionId: 'game', fetchImpl });
    const result = await execute({ name: 'reveal_all_secrets', arguments: {} });

    expect(result).toEqual(expect.objectContaining({ ok: false }));
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  test.each([
    [
      'advance_campaign_scene',
      { reason: 'The party follows the tracks to the chapel.' },
      '/director/advance',
      { reason: 'The party follows the tracks to the chapel.' },
    ],
    [
      'record_npc_reaction',
      { npc_id: 'mara-finch', reaction: 'trusts_more', reason: 'They promised to find Finn.' },
      '/director/npc-reaction',
      {
        npc_id: 'mara-finch',
        reaction: 'trusts_more',
        public_reason: 'They promised to find Finn.',
      },
    ],
    [
      'record_scene_discovery',
      { discovery: 'careful_observation', reason: 'They followed the fresh boot prints.' },
      '/director/discovery',
      {
        discovery: 'careful_observation',
        public_reason: 'They followed the fresh boot prints.',
      },
    ],
    [
      'award_character_currency',
      { player_id: 'player-one', amount: 25, denomination: 'gp', reason: 'Civic retainer.' },
      '/players/player-one/currency/award',
      { amount: 25, denomination: 'gp', reason: 'Civic retainer.' },
    ],
  ])('routes %s through the authoritative Director', async (name, args, path, expectedBody) => {
    const fetchImpl = jest.fn()
      .mockResolvedValueOnce(response({ state_version: 9 }))
      .mockResolvedValueOnce(response({ state_version: 10, performer_context: {} }));
    const execute = createGameToolExecutor({ sessionId: 'game', fetchImpl });

    const result = await execute({ name, callId: `call-${name}`, arguments: args });

    expect(result.ok).toBe(true);
    expect(fetchImpl.mock.calls[1][0]).toContain(path);
    expect(JSON.parse(fetchImpl.mock.calls[1][1].body)).toEqual(expect.objectContaining({
      ...expectedBody,
      expected_state_version: 9,
    }));
  });

  test('reads the performer projection without a mutation payload', async () => {
    const fetchImpl = jest.fn().mockResolvedValueOnce(response({
      state_version: 4,
      performer_context: { current_scene: { id: 'rainy-square' } },
    }));
    const execute = createGameToolExecutor({ sessionId: 'game', fetchImpl });

    const result = await execute({
      name: 'read_performer_context',
      callId: 'context-1',
      arguments: {},
    });

    expect(result.ok).toBe(true);
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    expect(fetchImpl.mock.calls[0][0]).toContain('/director');
    expect(fetchImpl.mock.calls[0][1].method).toBeUndefined();
  });
});
