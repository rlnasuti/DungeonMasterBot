const DEFAULT_API_BASE = (
  process.env.REACT_APP_API_BASE || 'http://localhost:8000'
).replace(/\/$/, '');

export class ConversationApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = 'ConversationApiError';
    this.status = status;
  }
}

function endpoint(apiBaseUrl, sessionId, suffix = '') {
  const base = (apiBaseUrl || DEFAULT_API_BASE).replace(/\/$/, '');
  return `${base}/api/sessions/${encodeURIComponent(sessionId)}/conversation${suffix}`;
}

async function parseResponse(response, fallbackMessage) {
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ConversationApiError(
      payload?.error?.message || fallbackMessage,
      response.status,
    );
  }
  return payload;
}

export async function readConversation({ sessionId, apiBaseUrl, fetchImpl = fetch }) {
  const response = await fetchImpl(endpoint(apiBaseUrl, sessionId), {
    headers: { Accept: 'application/json' },
  });
  return parseResponse(response, 'The Chronicle could not be restored.');
}

export async function writeConversationMessage({
  sessionId,
  messageId,
  role,
  text,
  apiBaseUrl,
  fetchImpl = fetch,
}) {
  const response = await fetchImpl(
    endpoint(
      apiBaseUrl,
      sessionId,
      `/messages/${encodeURIComponent(messageId)}`,
    ),
    {
      method: 'PUT',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: JSON.stringify({ role, text }),
    },
  );
  return parseResponse(response, 'The Chronicle entry could not be saved.');
}

export async function clearConversation({ sessionId, apiBaseUrl, fetchImpl = fetch }) {
  const response = await fetchImpl(endpoint(apiBaseUrl, sessionId), {
    method: 'DELETE',
    headers: { Accept: 'application/json' },
  });
  return parseResponse(response, 'The Chronicle could not be cleared.');
}
