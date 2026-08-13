/** PCM / capture constants aligned with the FastAPI RawPCMSerializer. */
export const SAMPLE_RATE_HZ = 16_000;

/**
 * Barge-in timing — ported from the working `client/agent.js`.
 * These are protocol-sensitive, not arbitrary UI delays.
 */
export const INTERRUPT_DEBOUNCE_MS = 220;
export const MIN_BOT_SPEAKING_MS_BEFORE_INTERRUPT = 400;
export const SERVER_BARGE_IN_RESET_MS = 800;
export const TRANSCRIPT_DEDUPE_MS = 3_000;
export const MIC_HEALTH_CHECK_MS = 5_000;
