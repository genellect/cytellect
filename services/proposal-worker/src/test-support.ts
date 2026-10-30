/** Test-only D1 stand-in: real SQLite (node:sqlite) with every committed migration. */
import type { D1Database } from "./store";

// Untyped dynamic imports: the Worker's own type set excludes Node APIs.
const sqliteModule = "node:sqlite";
const fsModule = "node:fs";

export const MIGRATIONS = ["0001_init.sql", "0002_usage_integrity.sql", "0003_budget_reconciliation.sql", "0004_cloud_access.sql"];

export async function sqliteDatabase(migrations = MIGRATIONS): Promise<D1Database> {
  const { DatabaseSync } = await import(sqliteModule);
  const { readFileSync } = await import(fsModule);
  const db = new DatabaseSync(":memory:");
  db.exec("PRAGMA foreign_keys = ON");
  for (const name of migrations) db.exec(readFileSync(new URL(`../migrations/${name}`, import.meta.url), "utf8"));
  const statement = (query: string, values: unknown[] = []) => ({
    query, values,
    bind: (...next: unknown[]) => statement(query, next),
    first: async () => db.prepare(query).get(...values) ?? null,
    run: async () => ({ meta: { changes: Number(db.prepare(query).run(...values).changes) } }),
    all: async () => ({ results: db.prepare(query).all(...values) }),
  });
  // D1's batch is one transaction: every statement or none.
  const batch = async (statements: { query: string; values: unknown[] }[]) => {
    db.exec("BEGIN");
    try {
      const results = statements.map((item) => ({ meta: { changes: Number(db.prepare(item.query).run(...item.values).changes) } }));
      db.exec("COMMIT");
      return results;
    } catch (error) {
      db.exec("ROLLBACK");
      throw error;
    }
  };
  return { prepare: (query: string) => statement(query), batch } as unknown as D1Database;
}
