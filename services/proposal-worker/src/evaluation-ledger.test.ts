import { afterEach, describe, expect, it } from "vitest";
import { EvaluationLedger } from "./evaluation-ledger";

const fsModule = "node:fs";
const osModule = "node:os";
const pathModule = "node:path";
const childModule = "node:child_process";
const processModule = "node:process";
const { mkdtempSync, mkdirSync, rmSync } = await import(fsModule);
const { tmpdir } = await import(osModule);
const { join } = await import(pathModule);
const { spawn } = await import(childModule);
const { execPath } = await import(processModule);
const folders: string[] = [];

function paths() {
  const root = mkdtempSync(join(tmpdir(), "cytellect-public-eval-"));
  folders.push(root);
  const checkout = join(root, "checkout");
  mkdirSync(checkout);
  return { checkout, ledger: join(root, "approved-evaluation.sqlite") };
}

afterEach(() => { for (const folder of folders.splice(0)) rmSync(folder, { recursive: true, force: true }); });

describe("durable public evaluation budget", () => {
  it("keeps interrupted holds across reopening and never resets the approved total", async () => {
    const p = paths();
    const first = await EvaluationLedger.open(p.ledger, p.checkout, 5, true);
    expect(first.reserve("public-case", 3)).not.toBeNull();
    first.close(); // Represents interruption after a committed hold, before settling.
    const resumed = await EvaluationLedger.open(p.ledger, p.checkout, 5);
    expect(resumed.accountedUsd()).toBe(3);
    expect(resumed.reserve("another-case", 2.000000001)).toBeNull();
    expect(resumed.reserve("another-case", 2)).not.toBeNull();
    expect(resumed.accountedUsd()).toBe(5);
    resumed.close();
    const again = await EvaluationLedger.open(p.ledger, p.checkout, 5);
    expect(again.reserve("retry", 0.000000001)).toBeNull();
    again.close();
  });

  it("settles once without losing durable historical spending", async () => {
    const p = paths();
    const first = await EvaluationLedger.open(p.ledger, p.checkout, 5, true);
    const id = first.reserve("public-case", 3)!;
    first.settle(id, 0.2, { inputTokens: 100, cachedInputTokens: 0, outputTokens: 200, calls: 1 });
    first.settle(id, 0);
    first.close();
    const resumed = await EvaluationLedger.open(p.ledger, p.checkout, 5);
    expect(resumed.accountedUsd()).toBe(0.2);
    expect(resumed.reserve("public-retry", 4.8)).not.toBeNull();
    expect(resumed.reserve("public-retry", 0.1)).toBeNull();
    resumed.close();
  });

  it("cannot increase a stored approval and refuses repository-local paths", async () => {
    const p = paths();
    await expect(EvaluationLedger.open(join(p.checkout, "ledger.sqlite"), p.checkout, 5)).rejects.toThrow("external_ledger");
    await expect(EvaluationLedger.open(p.ledger, p.checkout, 5.01)).rejects.toThrow("approval_limit");
    const first = await EvaluationLedger.open(p.ledger, p.checkout, 1, true);
    first.close();
    await expect(EvaluationLedger.open(p.ledger, p.checkout, 5)).rejects.toThrow("approval_mismatch");
  });

  it("blocks further calls if observed spending exceeds its reserved ceiling", async () => {
    const p = paths();
    const ledger = await EvaluationLedger.open(p.ledger, p.checkout, 5, true);
    const id = ledger.reserve("public-case", 1)!;
    expect(() => ledger.settle(id, 1.1)).toThrow("reconciliation_required");
    ledger.close();
    const resumed = await EvaluationLedger.open(p.ledger, p.checkout, 5);
    expect(() => resumed.reserve("next-case", 1)).toThrow("reconciliation_required");
    expect(resumed.accountedUsd()).toBe(1.1);
    resumed.close();
  });

  it("serializes admission in two independent processes under one total cap", async () => {
    const p = paths();
    const initial = await EvaluationLedger.open(p.ledger, p.checkout, 5, true);
    initial.close();
    const moduleUrl = new URL("./evaluation-ledger.ts", import.meta.url).href;
    const source = `import { EvaluationLedger } from ${JSON.stringify(moduleUrl)};
      const ledger = await EvaluationLedger.open(${JSON.stringify(p.ledger)}, ${JSON.stringify(p.checkout)}, 5);
      const id = ledger.reserve("public-concurrent", 3); ledger.close(); process.exit(id ? 0 : 2);`;
    const run = () => new Promise<number>((resolve, reject) => {
      const child = spawn(execPath, ["--input-type=module", "--eval", source], { stdio: "ignore" });
      child.once("error", reject);
      child.once("exit", (code: number | null) => resolve(code ?? -1));
    });
    expect((await Promise.all([run(), run()])).sort()).toEqual([0, 2]);
    const resumed = await EvaluationLedger.open(p.ledger, p.checkout, 5);
    expect(resumed.accountedUsd()).toBe(3);
    resumed.close();
  });

  it("cannot silently recreate a missing ledger after initialization", async () => {
    const p = paths();
    await expect(EvaluationLedger.open(p.ledger, p.checkout, 5)).rejects.toThrow("missing_or_invalid");
    const initialized = await EvaluationLedger.open(p.ledger, p.checkout, 5, true);
    initialized.reserve("public-case", 4);
    initialized.close();
    rmSync(p.ledger);
    await expect(EvaluationLedger.open(p.ledger, p.checkout, 5)).rejects.toThrow("missing_or_invalid");
  });

  it("retains a committed hold when the reserving process exits without closing", async () => {
    const p = paths();
    const initialized = await EvaluationLedger.open(p.ledger, p.checkout, 5, true);
    initialized.close();
    const moduleUrl = new URL("./evaluation-ledger.ts", import.meta.url).href;
    const source = `import { EvaluationLedger } from ${JSON.stringify(moduleUrl)};
      const ledger = await EvaluationLedger.open(${JSON.stringify(p.ledger)}, ${JSON.stringify(p.checkout)}, 5);
      ledger.reserve("public-interrupted", 4.5); process.exit(13);`;
    const code = await new Promise<number>((resolve, reject) => {
      const child = spawn(execPath, ["--input-type=module", "--eval", source], { stdio: "ignore" });
      child.once("error", reject);
      child.once("exit", (status: number | null) => resolve(status ?? -1));
    });
    expect(code).toBe(13);
    const resumed = await EvaluationLedger.open(p.ledger, p.checkout, 5);
    expect(resumed.accountedUsd()).toBe(4.5);
    expect(resumed.reserve("next-case", 0.6)).toBeNull();
    resumed.close();
  });
});
