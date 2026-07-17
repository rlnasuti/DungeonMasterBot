import { createGameApi } from './api';

test('updatePlayerIdentity sends the versioned idempotent PATCH contract', async () => {
  const fetchImpl = jest.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: jest.fn().mockResolvedValue({ state_version: 8, display_name: 'Robert' }),
  });
  const api = createGameApi('http://localhost:8000/', fetchImpl);
  const submission = {
    display_name: 'Robert',
    expected_state_version: 7,
    idempotency_key: 'setup:player-one:identity',
  };

  await expect(api.updatePlayerIdentity(
    'session/with slash',
    'player one',
    submission,
  )).resolves.toEqual({ state_version: 8, display_name: 'Robert' });

  expect(fetchImpl).toHaveBeenCalledWith(
    'http://localhost:8000/api/sessions/session%2Fwith%20slash/players/player%20one',
    expect.objectContaining({
      method: 'PATCH',
      headers: expect.objectContaining({
        'Content-Type': 'application/json',
        'Idempotency-Key': 'setup:player-one:identity',
      }),
      body: JSON.stringify(submission),
    }),
  );
});
