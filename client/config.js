/**
 * Resolves the WebSocket URL for Ministros.
 * Priority: ?ws= query → window.MINISTROS_WS_URL (config.js / build) → same-origin /ws
 */
(function () {
  const params = new URLSearchParams(window.location.search);
  const fromQuery = params.get('ws');
  if (fromQuery) {
    window.MINISTROS_WS_URL = fromQuery;
    return;
  }
  if (!window.MINISTROS_WS_URL) {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    window.MINISTROS_WS_URL = `${proto}//${window.location.host}/ws`;
  }
})();
