/** Durable accounting for the single approved public evaluation, never researcher data.
 * SQLite's file lock makes admission atomic across processes; no lease expiry releases
 * possibly billed reservations. This module is used only by the local evaluator.
 */
export const EVALUATION_APPROVAL = "cytellect-sol-public-2026-10-05";
export const APPROVED_TOTAL_USD = 5;
const SCALE = 1_000_000_000;
const fsModule = "node:fs";
const pathModule = "node:path";
const sqliteModule = "node:sqlite";

interface Database {
  exec(sql: string): void;
  prepare(sql: string): { get(...args: unknown[]): unknown; run(...args: unknown[]): unknown };
  close(): void;
}
interface Configuration { approval: string; cap_nano: number; blocked: number }
interface Hold { state: string; reserved_nano: number }
export interface EvalUsage { inputTokens: number; cachedInputTokens: number; outputTokens: number; calls: number }

function nano(usd: number): number {
  const value = Math.ceil(usd * SCALE);
  if (!Number.isFinite(usd) || usd < 0 || !Number.isSafeInteger(value)) throw new Error("evaluation_cost_invalid");
  return value;
}

export class EvaluationLedger {
  private readonly db: Database;
  private readonly cap: number;

  private constructor(db: Database, cap: number) { this.db = db; this.cap = cap; }

  static async open(filename: string, checkout: string, budgetUsd: number, initialize = false): Promise<EvaluationLedger> {
    if (!(budgetUsd > 0 && budgetUsd <= APPROVED_TOTAL_USD)) throw new Error("evaluation_approval_limit_invalid");
    const fs = await import(fsModule);
    const path = await import(pathModule);
    const { DatabaseSync } = await import(sqliteModule);
    if (!filename || !path.isAbsolute(filename)) throw new Error("evaluation_external_ledger_required");
    const root = fs.realpathSync(checkout);
    // Parent must already exist, outside Git. Resolve it before comparing to defeat symlink aliases.
    const parent = fs.realpathSync(path.dirname(filename));
    const target = path.join(parent, path.basename(filename));
    const relative = path.relative(root, target);
    if (!relative || (relative !== ".." && !relative.startsWith(`..${path.sep}`) && !path.isAbsolute(relative))) {
      throw new Error("evaluation_external_ledger_required");
    }
    let created = false;
    if (initialize) {
      try {
        const fd = fs.openSync(target, "wx", 0o600);
        fs.closeSync(fd);
        created = true;
      } catch (error) {
        if ((error as { code?: string }).code !== "EEXIST") throw new Error("evaluation_ledger_unavailable");
      }
    }
    if (!created) {
      try {
        const stat = fs.lstatSync(target);
        if (!stat.isFile() || stat.isSymbolicLink() || stat.nlink !== 1) throw new Error("invalid_source");
      } catch { throw new Error("evaluation_ledger_missing_or_invalid"); }
    }
    const db = new DatabaseSync(target) as Database;
    try {
      db.exec("PRAGMA busy_timeout=5000; PRAGMA synchronous=FULL;");
      if (created) {
        db.exec("BEGIN IMMEDIATE;");
        try {
          db.exec("CREATE TABLE approval (id INTEGER PRIMARY KEY CHECK (id=1), approval TEXT NOT NULL, cap_nano INTEGER NOT NULL, blocked INTEGER NOT NULL DEFAULT 0);"
            + "CREATE TABLE charges (id TEXT PRIMARY KEY, case_id TEXT NOT NULL, state TEXT NOT NULL CHECK (state IN ('held','settled')), reserved_nano INTEGER NOT NULL CHECK (reserved_nano>=0), spent_nano INTEGER, input_tokens INTEGER, cached_input_tokens INTEGER, output_tokens INTEGER, calls INTEGER);");
          db.prepare("INSERT INTO approval (id,approval,cap_nano) VALUES (1,?,?)").run(EVALUATION_APPROVAL, nano(budgetUsd));
          db.exec("COMMIT;");
        } catch { db.exec("ROLLBACK;"); throw new Error("evaluation_ledger_invalid"); }
      }
      const config = db.prepare("SELECT approval,cap_nano,blocked FROM approval WHERE id=1").get() as Configuration | undefined;
      if (!config || config.approval !== EVALUATION_APPROVAL || !Number.isSafeInteger(config.cap_nano)
        || config.cap_nano <= 0 || config.cap_nano > nano(APPROVED_TOTAL_USD) || nano(budgetUsd) > config.cap_nano) {
        throw new Error("evaluation_approval_mismatch");
      }
      return new EvaluationLedger(db, nano(budgetUsd));
    } catch { db.close(); throw new Error("evaluation_ledger_invalid_or_approval_mismatch"); }
  }

  private totalNano(): number {
    const row = this.db.prepare("SELECT COALESCE(SUM(CASE WHEN state='held' THEN reserved_nano ELSE spent_nano END),0) AS total FROM charges").get() as { total: number };
    if (!Number.isSafeInteger(row.total) || row.total < 0) throw new Error("evaluation_ledger_invalid");
    return row.total;
  }

  accountedUsd(): number { return this.totalNano() / SCALE; }

  /** Persist before any network call. Concurrent launches share the same file lock/cap. */
  reserve(caseId: string, amountUsd: number): string | null {
    if (!/^[a-z0-9-]{1,64}$/.test(caseId)) throw new Error("evaluation_case_invalid");
    const amount = nano(amountUsd);
    if (amount === 0) throw new Error("evaluation_cost_invalid");
    const id = crypto.randomUUID();
    this.db.exec("BEGIN IMMEDIATE;");
    try {
      const config = this.db.prepare("SELECT approval,cap_nano,blocked FROM approval WHERE id=1").get() as Configuration;
      if (config.blocked) throw new Error("evaluation_ledger_reconciliation_required");
      if (this.totalNano() + amount > Math.min(this.cap, config.cap_nano)) {
        this.db.exec("COMMIT;");
        return null;
      }
      this.db.prepare("INSERT INTO charges (id,case_id,state,reserved_nano) VALUES (?,?,'held',?)").run(id, caseId, amount);
      this.db.exec("COMMIT;");
      return id;
    } catch (error) { this.db.exec("ROLLBACK;"); throw error; }
  }

  /** Unknown billing stays held. Only known bounded usage may reduce a reservation. */
  settle(id: string, spentUsd: number, usage?: EvalUsage): void {
    const spent = nano(spentUsd);
    this.db.exec("BEGIN IMMEDIATE;");
    try {
      const hold = this.db.prepare("SELECT state,reserved_nano FROM charges WHERE id=?").get(id) as Hold | undefined;
      if (!hold) throw new Error("evaluation_reservation_missing");
      if (hold.state === "settled") { this.db.exec("COMMIT;"); return; }
      if (spent > hold.reserved_nano) {
        this.db.prepare("UPDATE charges SET state='settled',spent_nano=?,input_tokens=?,cached_input_tokens=?,output_tokens=?,calls=? WHERE id=?")
          .run(spent, usage?.inputTokens ?? null, usage?.cachedInputTokens ?? null, usage?.outputTokens ?? null, usage?.calls ?? null, id);
        this.db.exec("UPDATE approval SET blocked=1 WHERE id=1; COMMIT;");
        throw new Error("evaluation_ledger_reconciliation_required");
      }
      this.db.prepare("UPDATE charges SET state='settled',spent_nano=?,input_tokens=?,cached_input_tokens=?,output_tokens=?,calls=? WHERE id=? AND state='held'")
        .run(spent, usage?.inputTokens ?? null, usage?.cachedInputTokens ?? null, usage?.outputTokens ?? null, usage?.calls ?? null, id);
      this.db.exec("COMMIT;");
    } catch (error) {
      // A reconciliation block is intentionally committed, all other failures roll back.
      if (!(error instanceof Error && error.message === "evaluation_ledger_reconciliation_required")) this.db.exec("ROLLBACK;");
      throw error;
    }
  }

  close(): void { this.db.close(); }
}
