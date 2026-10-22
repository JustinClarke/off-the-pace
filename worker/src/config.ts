// Everything the browser must not control is fixed here.
export const MODEL = "@cf/openai/gpt-oss-20b";
export const MAX_OUTPUT_TOKENS = 800;
export const MAX_BODY_BYTES = 32 * 1024;
export const MAX_MESSAGES = 40;
export const MAX_MESSAGE_CHARS = 8000;
export const REASONING = { effort: "low" } as const;

// Placeholder: AI-04 owns the real system prompt and the seven tool definitions.
export const SYSTEM_PROMPT =
  "You are the Off the Pace assistant. Answer only from the app's published data and tools. State uncertainty plainly.";
export const TOOLS: unknown[] = [];

// Workers AI pricing, gpt-oss-20b, checked 2026-10-23
// https://developers.cloudflare.com/workers-ai/platform/pricing/
export const NEURONS_PER_M_INPUT = 18182;
export const NEURONS_PER_M_OUTPUT = 27273;

export const PAUSED_MESSAGE = "answers are paused for today";
