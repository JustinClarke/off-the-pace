export const SUMMARY_BUDGET_TOKENS: number
export const TOKEN_ESTIMATE: string
export const DOCS_APP_DIR: string
export const OUT_FILE: string
export const ASSISTANT_DOCS_DIR: string
export function assistantSourceFor(slug: string, dir?: string): string | null
export function estimateTokens(text: string): number
export function summarise(slug: string, src: string, budget?: number): { title: string; summary: string; tokens: number }
export function buildAll(
  docsDir?: string,
  assistantDir?: string,
): {
  tokenEstimate: string
  budgetTokens: number
  pages: Record<
    string,
    { title: string; summary: string; tokens: number; source?: string; sourceSha256?: string; docsSha256?: string }
  >
}
export function serialise(data: unknown): string
