/**
 * Server-side backend API helpers.
 *
 * Import from Next.js API routes (`app/api/**`) only. The browser talks to
 * same-origin `/api/*` routes; those routes proxy to Render via `backendJson`.
 *
 * Production: set `VOICE_API_URL=https://your-service.onrender.com` on Vercel.
 */

export { voiceApiUrl, backendJson } from "@/lib/server/backendApi";
