/** D1Store against real SQLite (node:sqlite) with the committed migration. */
import { describe, expect, it } from "vitest";
import { D1Store, type D1Database } from "./store";

// Untyped dynamic imports: the Worker's own type set excludes Node APIs.
const sqliteModule = "node:sqlite";
const fsModule = "node:fs";

async function database(): Promise<D1Database> {
  const { DatabaseSync } = await import(sqliteModule);
  const { readFileSync } = await import(fsModule);
  const db = new DatabaseSync(":memory:");
  db.exec(readFileSync(new URL("../migrations/0001_init.sql", import.meta.url), "utf8"));
  const statement = (query: string, values: unknown[] = []) => ({
    bind: (...next: unknown[]) => statement(query, next),
    first: async () => db.prepare(query).get(...values) ?? null,
    run: async () => ({ meta: { changes: Number(db.prepare(query).run(...values).changes) } }),
  });
  return { prepare: (query: string) => statement(query) } as unknown as D1Database;
}

describe("D1Store SQL", () => {
  it("redeems an invitation once and only before it expires", async () => {
    const store = new D1Store(await database());
    await store.createInvitation("inv", 1_000);
    expect(await store.redeemInvitation("inv", "dev", 2_000)).toBe(false);
    await store.createInvitation("inv2", 5_000);
    expect(await store.redeemInvitation("inv2", "dev", 2_000)).toBe(true);
    expect(await store.redeemInvitation("inv2", "dev-2", 2_001)).toBe(false);
    expect(await store.deviceActive("dev")).toBe(true);
    expect(await store.deviceActive("dev-2")).toBe(false);
  });

  it("counts device requests up to the monthly limit per month", async () => {
    const store = new D1Store(await database());
    const results = [];
    for (let index = 0; index < 4; index += 1) results.push(await store.countDeviceRequest("dev", "2026-10", 3));
    expect(results).toEqual([true, true, true, false]);
    expect(await store.countDeviceRequest("dev", "2026-11", 3)).toBe(true);
    expect(await store.countDeviceRequest("dev", "2026-12", 0)).toBe(false);
  });

  it("reserves within the budget, settles actual cost and keeps unsettled reservations counted", async () => {
    const store = new D1Store(await database());
    expect(await store.reserve("a", "2026-10", 0.6, 1, 0)).toBe(true);
    expect(await store.reserve("b", "2026-10", 0.6, 1, 1)).toBe(false);
    await store.settle("a", "2026-10", 0.25);
    expect(await store.unsettled("2026-10")).toBe(0);
    expect(await store.reserve("c", "2026-10", 0.7, 1, 2)).toBe(true);
    expect(await store.reserve("d", "2026-10", 0.1, 1, 86_400_000)).toBe(false);
    await store.settle("c", "2026-10", 0.5);
    expect(await store.reserve("e", "2026-10", 0.25, 1, 3)).toBe(true);
    expect(await store.reserve("f", "2026-11", 0.9, 1, 4)).toBe(true);
  });
});
