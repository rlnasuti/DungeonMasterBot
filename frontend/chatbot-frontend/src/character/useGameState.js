import { useCallback, useEffect, useRef, useState } from 'react';

function unwrapSnapshot(payload) {
  if (!payload || payload.unchanged) return null;
  if (payload.state && typeof payload.state === 'object') {
    return {
      ...payload.state,
      state_version: payload.state_version ?? payload.state.state_version,
    };
  }
  return payload;
}

export function useGameState({ sessionId, api, pollIntervalMs = 3000 }) {
  const [snapshot, setSnapshot] = useState(null);
  const [loading, setLoading] = useState(Boolean(sessionId));
  const [error, setError] = useState(null);
  const [submittingRollId, setSubmittingRollId] = useState(null);
  const versionRef = useRef(null);
  const mountedRef = useRef(true);

  useEffect(() => () => {
    mountedRef.current = false;
  }, []);

  const applyPayload = useCallback((payload) => {
    const next = unwrapSnapshot(payload);
    if (!next) return false;
    const containsParty = Array.isArray(next.players)
      || Array.isArray(next.characters)
      || Array.isArray(next.party?.players);
    if (!containsParty) {
      if (Number.isInteger(next.state_version)) {
        versionRef.current = next.state_version;
      }
      return false;
    }
    versionRef.current = next.state_version ?? versionRef.current;
    setSnapshot(next);
    return true;
  }, []);

  const refresh = useCallback(async ({ initial = false, signal } = {}) => {
    if (!sessionId) {
      setLoading(false);
      setSnapshot(null);
      return null;
    }

    if (initial) setLoading(true);
    try {
      const payload = await api.getGameState(sessionId, {
        sinceVersion: initial ? null : versionRef.current,
        signal,
      });
      if (!mountedRef.current) return payload;
      applyPayload(payload);
      setError(null);
      return payload;
    } catch (requestError) {
      if (requestError?.name === 'AbortError') return null;
      if (mountedRef.current) setError(requestError);
      return null;
    } finally {
      if (initial && mountedRef.current) setLoading(false);
    }
  }, [api, applyPayload, sessionId]);

  useEffect(() => {
    mountedRef.current = true;
    versionRef.current = null;
    setSnapshot(null);
    setError(null);
    const controller = new AbortController();
    let timerId = null;

    refresh({ initial: true, signal: controller.signal }).finally(() => {
      if (!controller.signal.aborted && pollIntervalMs > 0) {
        timerId = window.setInterval(
          () => refresh({ signal: controller.signal }),
          pollIntervalMs,
        );
      }
    });

    return () => {
      controller.abort();
      if (timerId !== null) window.clearInterval(timerId);
    };
  }, [pollIntervalMs, refresh, sessionId]);

  useEffect(() => {
    const refreshAfterMutation = () => refresh();
    window.addEventListener('dmb:game-state-changed', refreshAfterMutation);
    return () => window.removeEventListener('dmb:game-state-changed', refreshAfterMutation);
  }, [refresh]);

  const submitPhysicalRoll = useCallback(async ({ rollId, playerId, naturalRoll }) => {
    if (!rollId || !playerId || !sessionId) return false;

    const previousSnapshot = snapshot;
    setSubmittingRollId(rollId);
    setError(null);
    setSnapshot((current) => current ? {
      ...current,
      pending_roll: current.pending_roll ? {
        ...current.pending_roll,
        submission_status: 'submitting',
      } : current.pending_roll,
    } : current);

    try {
      const payload = await api.submitPhysicalRoll(sessionId, rollId, {
        player_id: playerId,
        natural_roll: naturalRoll,
        expected_state_version: versionRef.current,
      });
      if (!mountedRef.current) return true;
      if (!applyPayload(payload)) await refresh();
      if (payload?.roll_result) {
        window.dispatchEvent(new window.CustomEvent('dmb:physical-roll-resolved', {
          detail: payload.roll_result,
        }));
      }
      return true;
    } catch (requestError) {
      if (mountedRef.current) {
        setSnapshot(previousSnapshot);
        setError(requestError);
      }
      return false;
    } finally {
      if (mountedRef.current) setSubmittingRollId(null);
    }
  }, [api, applyPayload, refresh, sessionId, snapshot]);

  return {
    snapshot,
    loading,
    error,
    submittingRollId,
    refresh,
    submitPhysicalRoll,
  };
}
