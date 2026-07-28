/**
 * Writes config.generated.js from MINISTROS_WS_URL (Vercel env).
 * Example: wss://ministros-xxxx.onrender.com/ws
 */
const fs = require('fs');
const path = require('path');

const ws = (process.env.MINISTROS_WS_URL || '').trim();
const out = path.join(__dirname, 'config.generated.js');
const body = `window.MINISTROS_WS_URL = ${JSON.stringify(ws)};\n`;
fs.writeFileSync(out, body, 'utf8');
console.log(
  ws
    ? `[ministros] WS URL set for build: ${ws}`
    : '[ministros] MINISTROS_WS_URL empty — same-origin /ws will be used',
);
