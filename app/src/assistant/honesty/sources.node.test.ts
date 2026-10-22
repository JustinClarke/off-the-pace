// @vitest-environment node
// Every AI-02 rule and contradiction cites the line it came from. This test fails when a cited
// line no longer carries its quote, so a docs change shows up as a policy change to review.
// JSON logs are long single-line records that other sessions append to, so for them the quote
// must appear somewhere in the file and the line number is a hint only.
//
// A ref marked pending_commit cites text that exists only in an uncommitted file. It is checked
// against git HEAD, never the working tree, and shows as todo until HEAD carries the quote, so
// edits to the uncommitted file cannot break the policy. Only pending_ruling rules may use it.
import { describe, it, expect } from 'vitest'
import { readFileSync, existsSync } from 'node:fs'
import { execFileSync } from 'node:child_process'
import { join } from 'node:path'
import { policy, type SourceRef } from './checker'

const repoRoot = join(__dirname, '../../../..')

function checkRef(ref: SourceRef, label: string) {
  const path = join(repoRoot, ref.file)
  expect(existsSync(path), `${label}: ${ref.file} missing`).toBe(true)
  const text = readFileSync(path, 'utf8')
  if (ref.file.endsWith('.json') || ref.line === null) {
    expect(text.includes(ref.quote), `${label}: quote not found in ${ref.file}: ${ref.quote}`).toBe(true)
    return
  }
  const line = text.split('\n')[ref.line - 1] ?? ''
  expect(line.includes(ref.quote), `${label}: ${ref.file}:${ref.line} no longer says: ${ref.quote}`).toBe(true)
}

function committedText(file: string): string | null {
  try {
    return execFileSync('git', ['show', `HEAD:${file}`], { cwd: repoRoot, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'], maxBuffer: 64 * 1024 * 1024 })
  } catch {
    return null
  }
}

function citeTests(refs: SourceRef[], label: string, title: string, pendingAllowed: boolean) {
  const firm = refs.filter((s) => !s.pending_commit)
  const pending = refs.filter((s) => s.pending_commit)
  it(title, () => {
    expect(pendingAllowed || pending.length === 0, `${label}: pending_commit is only allowed on pending_ruling rules`).toBe(true)
    firm.forEach((s) => checkRef(s, label))
  })
  for (const s of pending) {
    const committed = committedText(s.file)
    if (committed !== null && committed.includes(s.quote)) {
      it(`${label} pending_commit quote is now at HEAD: ${s.quote}`, () => {
        expect(committed.includes(s.quote)).toBe(true)
      })
    } else {
      it.todo(`${label} cites uncommitted text, check once ${s.file} is committed: ${s.quote}`)
    }
  }
}

describe('AI-02 source citations', () => {
  for (const rule of policy.rules) {
    citeTests(rule.sources, rule.code, `${rule.code} cites lines that still say what the rule claims`, rule.status === 'pending_ruling')
  }
  for (const c of policy.contradictions) {
    citeTests(c.claims, c.id, `${c.id} (${c.topic}) cites both sides`, false)
  }
})
