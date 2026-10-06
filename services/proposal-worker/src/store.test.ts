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
  db.exec(readFileSync(new URL("../migrations/0002_usage_integrity.sql", import.meta.url), "utf8"));
  db.exec(readFileSync(new URL("../migrations/0003_budget_reconciliation.sql", import.meta.url), "utf8"));
  const statement = (query: string, values: unknown[] = []) => ({
    bind: (...next: unknown[]) => statement(query, next),
    first: async () => db.prepare(query).get(...values) ?? null,
    run: async () => ({ meta: { changes: Number(db.prepare(query).run(...values).changes) } }),
  });
  return { prepare: (query: string) => statement(query) } as unknown as D1Database;
}

describe("D1Store SQL", () => {
  it("atomically records overspending, preserves competing holds and blocks every month", async () => {
    const db = await database(), a = new D1Store(db), b = new D1Store(db);
    await a.reserve("overspend", "2026-10", 0.1, 5, 0);
    await b.reserve("in-flight", "2026-10", 0.2, 5, 1);
    const results = await Promise.all([
      a.settle("overspend", "2026-10", 0.3),
      b.reserve("racing", "2026-10", 0.1, 5, 2),
    ]);
    expect(results[1]).toBe(false);
    expect(await b.budgetBlocked()).toBe(true);
    expect(await b.unsettled("2026-10")).toBe(0.2);
    expect(await b.reserve("next-month", "2026-11", 0.1, 5, 3)).toBe(false);
    await a.settle("overspend", "2026-10", 9); // stale retry cannot change accounting
    await b.settle("in-flight", "2026-10", 0.05);
    expect(await db.prepare("SELECT spent_usd FROM usage_months WHERE month='2026-10'").first()).toEqual({ spent_usd: 0.35 });
    expect(await db.prepare("SELECT reserved_usd, accounted_usd, reason FROM budget_incidents").first())
      .toEqual({ reserved_usd: 0.1, accounted_usd: 0.3, reason: "reservation_exceeded" });
    expect(await b.budgetBlocked()).toBe(true);
    await db.prepare("UPDATE budget_incidents SET resolved_at=10, resolution_note='Reviewed tariff correction'").run();
    expect(await b.budgetBlocked()).toBe(false);
    expect(await b.reserve("retained-history", "2026-10", 4.66, 5, 11)).toBe(false);
  });

  it("latches a per-call ceiling violation even below the two-call reservation", async () => {
    const db = await database(), store = new D1Store(db);
    await store.reserve("bound", "2026-10", 0.5, 5, 0);
    await store.settle("bound", "2026-11", 0.1, undefined, true);
    expect(await store.budgetBlocked()).toBe(false);
    await store.settle("bound", "2026-10", 0.1, undefined, true);
    expect(await store.budgetBlocked()).toBe(true);
    expect(await db.prepare("SELECT reason FROM budget_incidents").first()).toEqual({ reason: "usage_ceiling_exceeded" });
  });

  it("rolls back incident and cost together if settlement cannot commit", async () => {
    const db = await database(), store = new D1Store(db);
    await store.reserve("failure", "2026-10", 0.1, 5, 0);
    await db.prepare("CREATE TRIGGER fail_delete BEFORE DELETE ON reservations BEGIN SELECT RAISE(ABORT, 'test'); END").run();
    await expect(store.settle("failure", "2026-10", 0.3)).rejects.toThrow();
    expect(await store.budgetBlocked()).toBe(false);
    expect(await store.unsettled("2026-10")).toBe(0.1);
    expect(await db.prepare("SELECT COUNT(*) AS n FROM settlements").first()).toEqual({ n: 0 });
    await db.prepare("DROP TRIGGER fail_delete").run();
    await store.settle("failure", "2026-10", 0.3);
    expect(await store.budgetBlocked()).toBe(true);
  });
  it("stores only accounting usage and provenance alongside conservative cost", async () => {
    const db = await database();
    const store = new D1Store(db);
    await store.reserve("metered", "2026-10", 0.8, 1, 0);
    await store.settle("metered", "2026-10", 0.2, { model: "gpt-6.1-sol", promptVersion: "2026-10-05.2", inputTokens: 1000, cachedInputTokens: 700, outputTokens: 200, calls: 1 });
    expect(await db.prepare("SELECT model, prompt_version, input_tokens, cached_input_tokens, output_tokens, calls FROM settlements WHERE id = ?").bind("metered").first())
      .toMatchObject({ model: "gpt-6.1-sol", prompt_version: "2026-10-05.2", input_tokens: 1000, cached_input_tokens: 700, output_tokens: 200, calls: 1 });
  });
  it("rolls back settlement accounting if removing the reservation fails", async () => {
    const db = await database();
    const store = new D1Store(db);
    await store.reserve("crash", "2026-10", 0.8, 1, 0);
    await db.prepare("CREATE TRIGGER test_failure BEFORE DELETE ON reservations BEGIN SELECT RAISE(ABORT, 'test'); END").run();
    await expect(store.settle("crash", "2026-10", 0.2)).rejects.toThrow();
    expect(await store.unsettled("2026-10")).toBe(0.8);
    await db.prepare("DROP TRIGGER test_failure").run();
    await store.settle("crash", "2026-10", 0.2);
    expect(await store.reserve("next", "2026-10", 0.8, 1, 1)).toBe(true);
  });
  it("claims action UUIDs once per device without storing research content", async () => {
    const store = new D1Store(await database());
    expect(await store.claimRequest("dev", "opaque-uuid", 0)).toBe(true);
    expect(await store.claimRequest("dev", "opaque-uuid", 1)).toBe(false);
    expect(await store.claimRequest("dev2", "opaque-uuid", 1)).toBe(true);
  });

  it("settlement retries and wrong-month settlement cannot double charge or lose a hold", async () => {
    const store = new D1Store(await database());
    await store.reserve("retry", "2026-10", 0.8, 1, 0);
    await store.settle("retry", "2026-11", 0.5);
    expect(await store.unsettled("2026-10")).toBe(0.8);
    await store.settle("retry", "2026-10", 0.2);
    await store.settle("retry", "2026-10", 0.2);
    expect(await store.unsettled("2026-10")).toBe(0);
    expect(await store.reserve("next", "2026-10", 0.8, 1, 0)).toBe(true);
  });
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
