import { describe, expect, it } from "vitest";
import { cpSync, mkdtempSync, readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
// @ts-expect-error plain .mjs
import { generate, LIMITS } from "../scripts/gen-tools.mjs";
import { CATALOGUE_VERSION, SYSTEM_PROMPT, TOOLS } from "../src/generated/tools";

const FIX = join(__dirname, "fixtures");
const PROMPT = join(__dirname, "../../app/src/assistant/prompt");
const opts = (dataDir = FIX) => ({ dataDir, systemPath: join(PROMPT, "system.md"), toolsPath: join(PROMPT, "tools.template.json"), playbookPath: join(PROMPT, "playbook.json") });

describe("gen-tools", () => {
  it("output carries the catalogue version and the seven tools with filled enums", () => {
    const r = generate(opts());
    const cat = JSON.parse(readFileSync(join(FIX, "assistant/catalogue.json"), "utf8"));
    expect(r.catalogue_version).toBe(cat.catalogue_version);
    expect(r.src).toContain(cat.catalogue_version);
    expect(TOOLS).toHaveLength(7);
    expect(r.src).toContain("qv_laps");
  });
  it("token bounds hold", () => {
    const r = generate(opts());
    expect(r.tokens.tools).toBeLessThanOrEqual(LIMITS.tools);
    expect(r.tokens.catalogue).toBeLessThanOrEqual(LIMITS.catalogue);
    expect(r.tokens.system).toBeLessThanOrEqual(LIMITS.system);
  });
  it("fails when the schemas exceed the bound", () => {
    const d = mkdtempSync(join(tmpdir(), "gt-"));
    const tpl = JSON.parse(readFileSync(join(PROMPT, "tools.template.json"), "utf8"));
    tpl.tools[0].function.description = "x".repeat(6000);
    writeFileSync(join(d, "t.json"), JSON.stringify(tpl));
    expect(() => generate({ ...opts(), toolsPath: join(d, "t.json") })).toThrow(/tool schemas/);
  });
  it("the committed generated file is not stale", () => {
    // Regenerating from the fixture catalogue (copied from the scratch export the file was made from) gives no diff.
    expect(generate(opts()).src).toBe(readFileSync(join(__dirname, "../src/generated/tools.ts"), "utf8"));
  });
  it("a changed catalogue changes the generated file (staleness is detected)", () => {
    const d = mkdtempSync(join(tmpdir(), "gt-"));
    mkdirSync(join(d, "assistant"));
    cpSync(join(FIX, "assistant"), join(d, "assistant"), { recursive: true });
    const p = join(d, "assistant/catalogue.json");
    const cat = JSON.parse(readFileSync(p, "utf8")); cat.catalogue_version = "f".repeat(64);
    writeFileSync(p, JSON.stringify(cat));
    expect(generate(opts(d)).src).not.toBe(readFileSync(join(__dirname, "../src/generated/tools.ts"), "utf8"));
  });
  it("the generated version equals the manifest's version when a manifest is given", () => {
    expect(CATALOGUE_VERSION).toBe(JSON.parse(readFileSync(join(FIX, "assistant/catalogue.json"), "utf8")).catalogue_version);
    expect(SYSTEM_PROMPT).toContain("Data views");
  });
});
