const DEFAULT_API_BASE = 'http://localhost:8000';

function withoutTrailingSlash(value) {
  return (value || DEFAULT_API_BASE).replace(/\/$/, '');
}

async function readJson(response) {
  let payload = null;
  try {
    payload = await response.json();
  } catch (_) {
    // The status still gives us a useful, non-sensitive fallback below.
  }

  if (!response.ok) {
    const publicMessage = payload?.error?.message || payload?.error || payload?.message;
    throw new Error(publicMessage || `Game state request failed (${response.status}).`);
  }
  return payload;
}

function idempotencyKey(callId, name) {
  const safeCallId = String(callId || 'unknown').replace(/[^A-Za-z0-9._:-]/g, '-');
  return `voice:${safeCallId}:${name}`.slice(0, 240);
}

/**
 * Execute only the fixed, player-visible tool vocabulary exposed to Realtime.
 * Optimistic versions and retry keys are added here, never supplied by the model.
 */
export function createGameToolExecutor({
  sessionId,
  apiBase = process.env.REACT_APP_API_BASE || DEFAULT_API_BASE,
  fetchImpl = window.fetch?.bind(window),
  onMutation,
} = {}) {
  if (!sessionId) throw new Error('A game session id is required.');
  if (!fetchImpl) throw new Error('A fetch implementation is required.');

  const base = withoutTrailingSlash(apiBase);
  const encodedSession = encodeURIComponent(sessionId);
  let queue = Promise.resolve();

  const request = async (path, options = {}) => {
    const response = await fetchImpl(`${base}${path}`, {
      headers: {
        Accept: 'application/json',
        ...(options.body ? { 'Content-Type': 'application/json' } : {}),
        ...options.headers,
      },
      ...options,
    });
    return readJson(response);
  };

  const readState = () => request(`/api/sessions/${encodedSession}/view`);

  const mutate = async (path, body, call) => {
    const state = await readState();
    const result = await request(path, {
      method: 'POST',
      body: JSON.stringify({
        ...body,
        expected_state_version: state.state_version,
        idempotency_key: idempotencyKey(call.callId, call.name),
      }),
    });
    onMutation?.(result);
    window.dispatchEvent(new window.Event('dmb:game-state-changed'));
    return { ok: true, result };
  };

  const executeOne = async (call) => {
    const args = call?.arguments || {};
    switch (call?.name) {
      case 'read_public_game_state':
        return { ok: true, state: await readState() };
      case 'read_performer_context':
        return {
          ok: true,
          context: await request(`/api/sessions/${encodedSession}/director`),
        };
      case 'request_physical_roll':
        return mutate(
          `/api/sessions/${encodedSession}/director/roll`,
          {
            player_id: args.player_id,
            roll_kind: args.roll_kind,
            ...(args.check_key ? { check_key: args.check_key } : {}),
            ...(args.difficulty ? { difficulty: args.difficulty } : {}),
            ...(args.dc_visibility ? { dc_visibility: args.dc_visibility } : {}),
            prompt: args.prompt,
          },
          call,
        );
      case 'apply_damage':
      case 'apply_healing': {
        const action = call.name === 'apply_damage' ? 'damage' : 'healing';
        return mutate(
          `/api/sessions/${encodedSession}/players/${encodeURIComponent(args.player_id)}/${action}`,
          { amount: args.amount },
          call,
        );
      }
      case 'use_character_resource':
      case 'restore_character_resource': {
        const action = call.name === 'use_character_resource' ? 'use' : 'restore';
        return mutate(
          `/api/sessions/${encodedSession}/players/${encodeURIComponent(args.player_id)}/resources/${action}`,
          {
            resource_type: args.resource_type,
            resource_key: args.resource_key,
            amount: args.amount,
          },
          call,
        );
      }
      case 'award_character_currency':
        return mutate(
          `/api/sessions/${encodedSession}/players/${encodeURIComponent(args.player_id)}/currency/award`,
          {
            amount: args.amount,
            denomination: args.denomination,
            reason: args.reason,
          },
          call,
        );
      case 'advance_campaign_scene':
        return mutate(
          `/api/sessions/${encodedSession}/director/advance`,
          { reason: args.reason },
          call,
        );
      case 'record_npc_reaction':
        return mutate(
          `/api/sessions/${encodedSession}/director/npc-reaction`,
          {
            npc_id: args.npc_id,
            reaction: args.reaction,
            public_reason: args.reason,
          },
          call,
        );
      case 'record_scene_discovery':
        return mutate(
          `/api/sessions/${encodedSession}/director/discovery`,
          {
            discovery: args.discovery,
            public_reason: args.reason,
          },
          call,
        );
      default:
        return {
          ok: false,
          error: {
            code: 'unknown_game_tool',
            message: 'That game action is not available.',
          },
        };
    }
  };

  return (call) => {
    const pending = queue.then(() => executeOne(call));
    queue = pending.catch(() => undefined);
    return pending;
  };
}
