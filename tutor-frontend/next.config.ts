import type { NextConfig } from "next";

const prodVoiceWs = process.env.NEXT_PUBLIC_VOICE_WS_URL ?? "";
if (
  process.env.NODE_ENV === "production" &&
  prodVoiceWs &&
  !prodVoiceWs.startsWith("wss://")
) {
  throw new Error(
    "NEXT_PUBLIC_VOICE_WS_URL must use wss:// in production (never ws://).",
  );
}

function voiceConnectSrc(): string {
  const raw = process.env.NEXT_PUBLIC_VOICE_WS_URL ?? "ws://127.0.0.1:8805/ws";
  try {
    const url = new URL(raw);
    const protocol =
      url.protocol === "https:" || url.protocol === "wss:" ? "wss:" : "ws:";
    const httpProtocol =
      url.protocol === "https:" || url.protocol === "wss:" ? "https:" : "http:";
    return `${protocol}//${url.host} ${httpProtocol}//${url.host}`;
  } catch {
    return "ws://127.0.0.1:8805 http://127.0.0.1:8805";
  }
}

const csp = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data:",
  "font-src 'self'",
  `connect-src 'self' ${voiceConnectSrc()}`,
  "media-src 'self' blob:",
  "worker-src 'self' blob:",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
].join("; ");

const nextConfig: NextConfig = {
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "Content-Security-Policy", value: csp },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          {
            key: "Permissions-Policy",
            value: "microphone=(self), camera=()",
          },
          ...(process.env.NODE_ENV === "production"
            ? [
                {
                  key: "Strict-Transport-Security",
                  value: "max-age=63072000; includeSubDomains; preload",
                },
              ]
            : []),
        ],
      },
    ];
  },
};

export default nextConfig;
