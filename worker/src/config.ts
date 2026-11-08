// Everything the browser must not control is fixed here.
export const MODEL = "@cf/openai/gpt-oss-20b";
// Provisional (design 2.6): AX-13 measures real output incl. reasoning tokens and sets the final value.
// Whether reasoning tokens count against this cap is UNVERIFIED (measure in AX-13). Do not raise without a measurement.
export const MAX_OUTPUT_TOKENS = 2500;
export const MAX_BODY_BYTES = 32 * 1024;
export const MAX_MESSAGES = 40;
export const MAX_MESSAGE_CHARS = 8000;
export const MAX_TOOL_MESSAGE_CHARS = 5000; // the tool-result slot (design 2.8)
export const MAX_ROUNDS = 5; // model rounds per question: 4 tool calls plus the final answer
export const TICKET_TTL_S = 120;
export const DEFAULT_VISITOR_DAILY_LIMIT = 3; // questions, not rounds (HD6)
export const DEFAULT_DAILY_NEURON_CAP = 10000; // the free allowance (AD4-B, HD6)
export const REASONING = { effort: "low" } as const;

// AX-08: the system prompt, the seven tool schemas and CATALOGUE_VERSION are generated from the exported
// catalogue (npm run gen-tools), so the Worker and the app cannot disagree.
export { SYSTEM_PROMPT, TOOLS, CATALOGUE_VERSION } from "./generated/tools";

// Workers AI pricing, gpt-oss-20b, checked 2026-10-23
// https://developers.cloudflare.com/workers-ai/platform/pricing/
export const NEURONS_PER_M_INPUT = 18182;
export const NEURONS_PER_M_OUTPUT = 27273;

export const PAUSED_MESSAGE = "answers are paused for today";
