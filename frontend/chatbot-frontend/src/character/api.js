const DEFAULT_BASE_URL = 'http://localhost:8000';

function trimTrailingSlash(value) {
  return (value || DEFAULT_BASE_URL).replace(/\/$/, '');
}

async function readJson(response) {
  if (response.status === 204 || response.status === 304) {
    return { unchanged: true };
  }

  let payload = null;
  try {
    payload = await response.json();
  } catch (_) {
    // Preserve the HTTP status below when an upstream error has no JSON body.
  }

  if (!response.ok) {
    const message = payload?.error?.message || payload?.error || payload?.message;
    throw new Error(message || `Game API request failed (${response.status})`);
  }

  return payload;
}

export function createGameApi(baseUrl = DEFAULT_BASE_URL, fetchImpl = window.fetch.bind(window)) {
  const root = trimTrailingSlash(baseUrl);

  return {
    async getGameState(sessionId, { sinceVersion, signal } = {}) {
      const encodedSessionId = encodeURIComponent(sessionId);
      const url = new URL(`${root}/api/sessions/${encodedSessionId}/view`);
      if (sinceVersion !== undefined && sinceVersion !== null) {
        url.searchParams.set('since_version', String(sinceVersion));
      }

      const response = await fetchImpl(url.toString(), {
        method: 'GET',
        headers: { Accept: 'application/json' },
        signal,
      });
      return readJson(response);
    },

    async submitPhysicalRoll(sessionId, rollId, submission, { signal } = {}) {
      const encodedSessionId = encodeURIComponent(sessionId);
      const encodedRollId = encodeURIComponent(rollId);
      const response = await fetchImpl(
        `${root}/api/sessions/${encodedSessionId}/rolls/${encodedRollId}`,
        {
          method: 'POST',
          headers: {
            Accept: 'application/json',
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(submission),
          signal,
        },
      );
      return readJson(response);
    },

    async updatePlayerIdentity(sessionId, playerId, submission, { signal } = {}) {
      const encodedSessionId = encodeURIComponent(sessionId);
      const encodedPlayerId = encodeURIComponent(playerId);
      const response = await fetchImpl(
        `${root}/api/sessions/${encodedSessionId}/players/${encodedPlayerId}`,
        {
          method: 'PATCH',
          headers: {
            Accept: 'application/json',
            'Content-Type': 'application/json',
            'Idempotency-Key': submission.idempotency_key,
          },
          body: JSON.stringify(submission),
          signal,
        },
      );
      return readJson(response);
    },

    async stageCharacter(sessionId, playerId, submission, { signal } = {}) {
      const encodedSessionId = encodeURIComponent(sessionId);
      const encodedPlayerId = encodeURIComponent(playerId);
      const response = await fetchImpl(
        `${root}/api/sessions/${encodedSessionId}/players/${encodedPlayerId}/character`,
        {
          method: 'POST',
          headers: {
            Accept: 'application/json',
            'Content-Type': 'application/json',
            'Idempotency-Key': submission.idempotency_key,
          },
          body: JSON.stringify(submission),
          signal,
        },
      );
      return readJson(response);
    },

    async confirmCharacter(sessionId, playerId, submission, { signal } = {}) {
      const encodedSessionId = encodeURIComponent(sessionId);
      const encodedPlayerId = encodeURIComponent(playerId);
      const response = await fetchImpl(
        `${root}/api/sessions/${encodedSessionId}/players/${encodedPlayerId}/character/confirm`,
        {
          method: 'POST',
          headers: {
            Accept: 'application/json',
            'Content-Type': 'application/json',
            'Idempotency-Key': submission.idempotency_key,
          },
          body: JSON.stringify(submission),
          signal,
        },
      );
      return readJson(response);
    },
  };
}
