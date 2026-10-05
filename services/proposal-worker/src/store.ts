/**
 * Rights and usage only. Research images, goals and prompt bodies are never
 * written here (requirement L04).
 */

/** Minimal subset of the Cloudflare D1 binding used by this service. */
export interface D1Result { meta: { changes: number } }
export interface D1Statement {
  bind(...values: unknown[]): D1Statement;
  first<T = Record<string, unknown>>(): Promise<T | null>;
  run(): Promise<D1Result>;
}
export interface D1Database { prepare(query: string): D1Statement }
export interface UsageRecord {
  model: string;
  promptVersion: string;
  inputTokens: number;
  cachedInputTokens: number;
  outputTokens: number;
  calls: number;
}

export interface Store {
  createInvitation(hash: string, expiresAt: number): Promise<void>;
  /** Marks the invitation used and registers the device; false when invalid, used or expired. */
  redeemInvitation(hash: string, deviceHash: string, now: number): Promise<boolean>;
  deviceActive(deviceHash: string): Promise<boolean>;
  /** Claim an opaque action UUID once; never stores request content or response. */
  claimRequest(deviceHash: string, requestId: string, now: number): Promise<boolean>;
  /** Counts one request for the device in the month; false when its quota is used. */
  countDeviceRequest(deviceHash: string, month: string, limit: number): Promise<boolean>;
  /**
   * Atomically reserves the worst-case cost; false when it would exceed the monthly budget.
   * A reservation that is never settled (a crashed request whose call may have been billed)
   * keeps counting at its worst case, so the budget is never exceeded by lost settlements.
   */
  reserve(id: string, month: string, amountUsd: number, budgetUsd: number, now: number): Promise<boolean>;
  /** Worst-case cost still held by reservations that were never settled. */
  unsettled(month: string): Promise<number>;
  /** Releases the reservation and records the conservative accounted cost. */
  settle(id: string, month: string, spentUsd: number, usage?: UsageRecord): Promise<void>;
}


export class D1Store implements Store {
  constructor(private readonly db: D1Database) {}

  async createInvitation(hash: string, expiresAt: number) {
    await this.db.prepare("INSERT INTO invitations (hash, expires_at) VALUES (?, ?)").bind(hash, expiresAt).run();
  }

  async redeemInvitation(hash: string, deviceHash: string, now: number) {
    const used = await this.db.prepare(
      "UPDATE invitations SET redeemed_at = ? WHERE hash = ? AND redeemed_at IS NULL AND expires_at > ?",
    ).bind(now, hash, now).run();
    if (used.meta.changes !== 1) return false;
    await this.db.prepare("INSERT INTO devices (hash, created_at) VALUES (?, ?)").bind(deviceHash, now).run();
    return true;
  }

  async deviceActive(deviceHash: string) {
    return (await this.db.prepare("SELECT 1 AS ok FROM devices WHERE hash = ? AND revoked_at IS NULL").bind(deviceHash).first()) !== null;
  }

  async claimRequest(deviceHash: string, requestId: string, now: number) {
    const result = await this.db.prepare("INSERT OR IGNORE INTO proposal_requests (device, request_id, created_at) VALUES (?, ?, ?)")
      .bind(deviceHash, requestId, now).run();
    return result.meta.changes === 1;
  }

  async countDeviceRequest(deviceHash: string, month: string, limit: number) {
    const result = await this.db.prepare(
      "INSERT INTO device_usage (device, month, requests) SELECT ?, ?, 1 WHERE ? > 0 "
      + "ON CONFLICT (device, month) DO UPDATE SET requests = requests + 1 WHERE requests < ?",
    ).bind(deviceHash, month, limit, limit).run();
    return result.meta.changes === 1;
  }

  async reserve(id: string, month: string, amountUsd: number, budgetUsd: number, now: number) {
    // One statement: SQLite serializes writes, so concurrent requests cannot both pass the check.
    const result = await this.db.prepare(
      "INSERT INTO reservations (id, month, amount_usd, created_at) SELECT ?, ?, ?, ? WHERE "
      + "COALESCE((SELECT spent_usd FROM usage_months WHERE month = ?), 0) + "
      + "COALESCE((SELECT SUM(amount_usd) FROM reservations WHERE month = ?), 0) + ? <= ?",
    ).bind(id, month, amountUsd, now, month, month, amountUsd, budgetUsd).run();
    return result.meta.changes === 1;
  }

  async unsettled(month: string) {
    const row = await this.db.prepare("SELECT COALESCE(SUM(amount_usd), 0) AS held FROM reservations WHERE month = ?")
      .bind(month).first<{ held: number }>();
    return row?.held ?? 0;
  }

  async settle(id: string, month: string, spentUsd: number, usage?: UsageRecord) {
    // One insertion + migration trigger atomically adds usage and removes the hold.
    // Repeated settlement or a failure after a successful commit cannot double count.
    await this.db.prepare(
      "INSERT OR IGNORE INTO settlements (id, month, spent_usd, model, prompt_version, input_tokens, cached_input_tokens, output_tokens, calls) "
      + "SELECT id, month, ?, ?, ?, ?, ?, ?, ? FROM reservations WHERE id = ? AND month = ?",
    ).bind(spentUsd, usage?.model ?? null, usage?.promptVersion ?? null, usage?.inputTokens ?? null,
      usage?.cachedInputTokens ?? null, usage?.outputTokens ?? null, usage?.calls ?? null, id, month).run();
  }
}

/** In-memory store with the same semantics, for tests and local development. */
export class MemoryStore implements Store {
  invitations = new Map<string, { expiresAt: number; redeemed: boolean }>();
  devices = new Map<string, { revoked: boolean }>();
  requests = new Map<string, number>();
  spent = new Map<string, number>();
  reservations = new Map<string, { month: string; amount: number; createdAt: number }>();
  claimedRequests = new Set<string>();
  usage = new Map<string, UsageRecord>();

  async createInvitation(hash: string, expiresAt: number) { this.invitations.set(hash, { expiresAt, redeemed: false }); }

  async redeemInvitation(hash: string, deviceHash: string, now: number) {
    const invitation = this.invitations.get(hash);
    if (!invitation || invitation.redeemed || invitation.expiresAt <= now) return false;
    invitation.redeemed = true;
    this.devices.set(deviceHash, { revoked: false });
    return true;
  }

  async deviceActive(deviceHash: string) { return this.devices.get(deviceHash)?.revoked === false; }

  async claimRequest(deviceHash: string, requestId: string, _now: number) {
    const key = `${deviceHash}:${requestId}`;
    if (this.claimedRequests.has(key)) return false;
    this.claimedRequests.add(key);
    return true;
  }

  async countDeviceRequest(deviceHash: string, month: string, limit: number) {
    const key = `${deviceHash}:${month}`;
    const used = this.requests.get(key) ?? 0;
    if (used >= limit) return false;
    this.requests.set(key, used + 1);
    return true;
  }

  async reserve(id: string, month: string, amountUsd: number, budgetUsd: number, now: number) {
    const held = [...this.reservations.values()].filter((item) => item.month === month).reduce((sum, item) => sum + item.amount, 0);
    if (this.reservations.has(id) || (this.spent.get(month) ?? 0) + held + amountUsd > budgetUsd) return false;
    this.reservations.set(id, { month, amount: amountUsd, createdAt: now });
    return true;
  }

  async unsettled(month: string) {
    return [...this.reservations.values()].filter((item) => item.month === month).reduce((sum, item) => sum + item.amount, 0);
  }

  async settle(id: string, month: string, spentUsd: number, usage?: UsageRecord) {
    if (this.reservations.get(id)?.month !== month) return;
    if (usage) this.usage.set(id, usage);
    this.spent.set(month, (this.spent.get(month) ?? 0) + spentUsd);
    this.reservations.delete(id);
  }
}
