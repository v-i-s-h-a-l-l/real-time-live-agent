/**
 * Resolves the WebSocket URL for Ministros.
 * Priority: ?ws= query → window.MINISTROS_WS_URL → localhost same-origin → Render prod
 */
(function () {
  const params = new URLSearchParams(window.location.search);
  const fromQuery = params.get('ws');
  if (fromQuery) {
    window.MINISTROS_WS_URL = fromQuery;
    return;
  }

  if (window.MINISTROS_WS_URL && String(window.MINISTROS_WS_URL).trim()) {
    return;
  }

  const host = window.location.hostname;
  const isLocal = host === 'localhost' || host === '127.0.0.1';
  if (isLocal) {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    window.MINISTROS_WS_URL = `${proto}//${window.location.host}/ws`;
    return;
  }

  // Production static host (Vercel) → Render backend
  window.MINISTROS_WS_URL = 'wss://real-time-live-agent.onrender.com/ws';
})();
