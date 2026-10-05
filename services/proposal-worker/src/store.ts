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

export interface Store {
  createInvitation(hash: string, expiresAt: number): Promise<void>;
  /** Marks the invitation used and registers the device; false when invalid, used or expired. */
  redeemInvitation(hash: string, deviceHash: string, now: number): Promise<boolean>;
  deviceActive(deviceHash: string): Promise<boolean>;
  /** Counts one request for the device in the month; false when its quota is used. */
  countDeviceRequest(deviceHash: string, month: string, limit: number): Promise<boolean>;
  /** Atomically reserves the worst-case cost; false when it would exceed the monthly budget. */
  reserve(id: string, month: string, amountUsd: number, budgetUsd: number, now: number): Promise<boolean>;
  /** Releases the reservation and records the actual cost. */
  settle(id: string, month: string, spentUsd: number): Promise<void>;
}

/** Reservations older than this no longer hold budget (a crashed request). */
export const RESERVATION_TTL_MS = 10 * 60 * 1000;

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
      + "COALESCE((SELECT SUM(amount_usd) FROM reservations WHERE month = ? AND created_at > ?), 0) + ? <= ?",
    ).bind(id, month, amountUsd, now, month, month, now - RESERVATION_TTL_MS, amountUsd, budgetUsd).run();
    return result.meta.changes === 1;
  }

  async settle(id: string, month: string, spentUsd: number) {
    await this.db.prepare(
      "INSERT INTO usage_months (month, spent_usd) VALUES (?, ?) ON CONFLICT (month) DO UPDATE SET spent_usd = spent_usd + excluded.spent_usd",
    ).bind(month, spentUsd).run();
    await this.db.prepare("DELETE FROM reservations WHERE id = ?").bind(id).run();
  }
}

/** In-memory store with the same semantics, for tests and local development. */
export class MemoryStore implements Store {
  invitations = new Map<string, { expiresAt: number; redeemed: boolean }>();
  devices = new Map<string, { revoked: boolean }>();
  requests = new Map<string, number>();
  spent = new Map<string, number>();
  reservations = new Map<string, { month: string; amount: number; createdAt: number }>();

  async createInvitation(hash: string, expiresAt: number) { this.invitations.set(hash, { expiresAt, redeemed: false }); }

  async redeemInvitation(hash: string, deviceHash: string, now: number) {
    const invitation = this.invitations.get(hash);
    if (!invitation || invitation.redeemed || invitation.expiresAt <= now) return false;
    invitation.redeemed = true;
    this.devices.set(deviceHash, { revoked: false });
    return true;
  }

  async deviceActive(deviceHash: string) { return this.devices.get(deviceHash)?.revoked === false; }

  async countDeviceRequest(deviceHash: string, month: string, limit: number) {
    const key = `${deviceHash}:${month}`;
    const used = this.requests.get(key) ?? 0;
    if (used >= limit) return false;
    this.requests.set(key, used + 1);
    return true;
  }

  async reserve(id: string, month: string, amountUsd: number, budgetUsd: number, now: number) {
    const held = [...this.reservations.values()]
      .filter((item) => item.month === month && item.createdAt > now - RESERVATION_TTL_MS)
      .reduce((sum, item) => sum + item.amount, 0);
    if ((this.spent.get(month) ?? 0) + held + amountUsd > budgetUsd) return false;
    this.reservations.set(id, { month, amount: amountUsd, createdAt: now });
    return true;
  }

  async settle(id: string, month: string, spentUsd: number) {
    this.spent.set(month, (this.spent.get(month) ?? 0) + spentUsd);
    this.reservations.delete(id);
  }
}
