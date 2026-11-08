// AX-10 (Node only): build the tool schemas and the system prompt the Worker would serve, in memory, with
// the AX-08 generator (worker/scripts/gen-tools.mjs `generate`). The committed worker/src/generated/tools.ts
// is built from an older card index, so a headless run that must offer every registry kind (held classes
// included) generates fresh from the catalogue + the registry's kinds instead. Writes only to a temp folder.
import { cpSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import type { ToolDef } from './validateArgs'

export interface GeneratedTools {
  tools: ToolDef[]
  system: string
  catalogue_version: string
  tokens: { tools: number; catalogue: number; system: number }
}

export async function generateTools(opts: { catalogueJson: string; kinds: readonly string[]; appDir: string }): Promise<GeneratedTools> {
  const dir = mkdtempSync(join(tmpdir(), 'ax10-gen-'))
  try {
    mkdirSync(join(dir, 'assistant'), { recursive: true })
    cpSync(opts.catalogueJson, join(dir, 'assistant', 'catalogue.json'))
    writeFileSync(join(dir, 'assistant', 'index.json'), JSON.stringify({ kinds: opts.kinds.map((kind) => ({ kind })) }))
    const genPath = resolve(opts.appDir, '../worker/scripts/gen-tools.mjs')
    const gen = (await import(/* @vite-ignore */ genPath)) as {
      generate(a: { dataDir: string; systemPath: string; toolsPath: string; playbookPath: string }): { src: string; tokens: GeneratedTools['tokens']; catalogue_version: string }
    }
    const prompts = resolve(opts.appDir, 'src/assistant/prompt')
    const r = gen.generate({
      dataDir: dir,
      systemPath: join(prompts, 'system.md'),
      toolsPath: join(prompts, 'tools.template.json'),
      playbookPath: join(prompts, 'playbook.json'),
    })
    const grab = (name: string): string => {
      const m = new RegExp(`export const ${name}(?:: unknown\\[\\])? = ([\\s\\S]*?);\\n(?:export const|$)`).exec(r.src)
      if (!m) throw new Error(`generated source has no ${name}`)
      return m[1]
    }
    return {
      tools: JSON.parse(grab('TOOLS')) as ToolDef[],
      system: JSON.parse(grab('SYSTEM_PROMPT')) as string,
      catalogue_version: r.catalogue_version,
      tokens: r.tokens,
    }
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
}
