/**
 * Rights and usage only. Research images, goals and prompt bodies are never
 * written here (requirement L04).
 */

/** Minimal subset of the Cloudflare D1 binding used by this service. */
export interface D1Result { meta: { changes: number } }
export interface D1Statement {
  bind(...values: unknown[]): D1Statement;
  first<T = Record<string, unknown>>(): Promise<T | null>;
  all<T = Record<string, unknown>>(): Promise<{ results: T[] }>;
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

/** What the operator sees per installation: no token, hash or research content. */
export interface DeviceRecord {
  id: string;
  label: string | null;
  created_at: number;
  revoked_at: number | null;
  proposals: number;
  cellpose_fields: number;
}

export interface Store {
  createInvitation(hash: string, expiresAt: number, label?: string | null): Promise<void>;
  /** Marks the invitation used and registers the device; false when invalid, used or expired. */
  redeemInvitation(hash: string, deviceHash: string, now: number, deviceId?: string): Promise<boolean>;
  deviceActive(deviceHash: string): Promise<boolean>;
  /** The active device's own record for the month; null when unknown or revoked. */
  deviceStatus(deviceHash: string, month: string): Promise<DeviceRecord | null>;
  listDevices(month: string): Promise<DeviceRecord[]>;
  /** Revokes by public id; false when no active device has it. */
  revokeDevice(id: string, now: number): Promise<boolean>;
  /** Counts one Cellpose field against the device and the whole service; false when either is used up. */
  reserveCellpose(deviceHash: string, month: string, deviceLimit: number, totalLimit: number): Promise<boolean>;
  /** Returns a field whose inference did not complete. */
  releaseCellpose(deviceHash: string, month: string): Promise<void>;
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
  /** Global hold persists across months until operator reconciliation. */
  budgetBlocked(): Promise<boolean>;
  /** Releases the reservation and records the conservative accounted cost. */
  settle(id: string, month: string, spentUsd: number, usage?: UsageRecord, ceilingExceeded?: boolean): Promise<void>;
}


export class D1Store implements Store {
  constructor(private readonly db: D1Database) {}

  async createInvitation(hash: string, expiresAt: number, label: string | null = null) {
    await this.db.prepare("INSERT INTO invitations (hash, expires_at, label) VALUES (?, ?, ?)").bind(hash, expiresAt, label).run();
  }

  async redeemInvitation(hash: string, deviceHash: string, now: number, deviceId = deviceHash.slice(0, 16)) {
    const used = await this.db.prepare(
      "UPDATE invitations SET redeemed_at = ? WHERE hash = ? AND redeemed_at IS NULL AND expires_at > ?",
    ).bind(now, hash, now).run();
    if (used.meta.changes !== 1) return false;
    await this.db.prepare("INSERT INTO devices (hash, created_at, id, label) SELECT ?, ?, ?, label FROM invitations WHERE hash = ?")
      .bind(deviceHash, now, deviceId, hash).run();
    return true;
  }

  async deviceActive(deviceHash: string) {
    return (await this.db.prepare("SELECT 1 AS ok FROM devices WHERE hash = ? AND revoked_at IS NULL").bind(deviceHash).first()) !== null;
  }

  private static readonly RECORD = "SELECT d.id, d.label, d.created_at, d.revoked_at, "
    + "COALESCE((SELECT requests FROM device_usage WHERE device = d.hash AND month = ?), 0) AS proposals, "
    + "COALESCE((SELECT fields FROM cellpose_usage WHERE device = d.hash AND month = ?), 0) AS cellpose_fields FROM devices d";

  async deviceStatus(deviceHash: string, month: string) {
    return this.db.prepare(`${D1Store.RECORD} WHERE d.hash = ? AND d.revoked_at IS NULL`)
      .bind(month, month, deviceHash).first<DeviceRecord>();
  }

  async listDevices(month: string) {
    return (await this.db.prepare(`${D1Store.RECORD} ORDER BY d.created_at`).bind(month, month).all<DeviceRecord>()).results;
  }

  async revokeDevice(id: string, now: number) {
    const result = await this.db.prepare("UPDATE devices SET revoked_at = ? WHERE id = ? AND revoked_at IS NULL").bind(now, id).run();
    return result.meta.changes === 1;
  }

  async reserveCellpose(deviceHash: string, month: string, deviceLimit: number, totalLimit: number) {
    // Each counter is one conditional statement; the service-wide one goes first and
    // is returned when the device's own limit refuses, so neither can be exceeded.
    const total = await this.db.prepare(
      "INSERT INTO cellpose_months (month, fields) SELECT ?, 1 WHERE ? > 0 "
      + "ON CONFLICT (month) DO UPDATE SET fields = fields + 1 WHERE fields < ?",
    ).bind(month, totalLimit, totalLimit).run();
    if (total.meta.changes !== 1) return false;
    const device = await this.db.prepare(
      "INSERT INTO cellpose_usage (device, month, fields) SELECT ?, ?, 1 WHERE ? > 0 "
      + "ON CONFLICT (device, month) DO UPDATE SET fields = fields + 1 WHERE fields < ?",
    ).bind(deviceHash, month, deviceLimit, deviceLimit).run();
    if (device.meta.changes === 1) return true;
    await this.db.prepare("UPDATE cellpose_months SET fields = fields - 1 WHERE month = ? AND fields > 0").bind(month).run();
    return false;
  }

  async releaseCellpose(deviceHash: string, month: string) {
    await this.db.prepare("UPDATE cellpose_usage SET fields = fields - 1 WHERE device = ? AND month = ? AND fields > 0")
      .bind(deviceHash, month).run();
    await this.db.prepare("UPDATE cellpose_months SET fields = fields - 1 WHERE month = ? AND fields > 0").bind(month).run();
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
      + "NOT EXISTS (SELECT 1 FROM budget_incidents WHERE resolved_at IS NULL) AND "
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

  async budgetBlocked() {
    return (await this.db.prepare("SELECT 1 FROM budget_incidents WHERE resolved_at IS NULL LIMIT 1").first()) !== null;
  }

  async settle(id: string, month: string, spentUsd: number, usage?: UsageRecord, ceilingExceeded = false) {
    // One insertion + migration trigger atomically adds usage and removes the hold.
    // Repeated settlement or a failure after a successful commit cannot double count.
    await this.db.prepare(
      "INSERT OR IGNORE INTO settlements (id, month, spent_usd, model, prompt_version, input_tokens, cached_input_tokens, output_tokens, calls, ceiling_exceeded) "
      + "SELECT id, month, ?, ?, ?, ?, ?, ?, ?, ? FROM reservations WHERE id = ? AND month = ?",
    ).bind(spentUsd, usage?.model ?? null, usage?.promptVersion ?? null, usage?.inputTokens ?? null,
      usage?.cachedInputTokens ?? null, usage?.outputTokens ?? null, usage?.calls ?? null, Number(ceilingExceeded), id, month).run();
  }
}

/** In-memory store with the same semantics, for tests and local development. */
export class MemoryStore implements Store {
  invitations = new Map<string, { expiresAt: number; redeemed: boolean; label: string | null }>();
  devices = new Map<string, { id: string; label: string | null; createdAt: number; revokedAt: number | null }>();
  cellpose = new Map<string, number>();
  requests = new Map<string, number>();
  spent = new Map<string, number>();
  reservations = new Map<string, { month: string; amount: number; createdAt: number }>();
  claimedRequests = new Set<string>();
  usage = new Map<string, UsageRecord>();
  blocked = false;

  async createInvitation(hash: string, expiresAt: number, label: string | null = null) {
    this.invitations.set(hash, { expiresAt, redeemed: false, label });
  }

  async redeemInvitation(hash: string, deviceHash: string, now: number, deviceId = deviceHash.slice(0, 16)) {
    const invitation = this.invitations.get(hash);
    if (!invitation || invitation.redeemed || invitation.expiresAt <= now) return false;
    invitation.redeemed = true;
    this.devices.set(deviceHash, { id: deviceId, label: invitation.label, createdAt: now, revokedAt: null });
    return true;
  }

  async deviceActive(deviceHash: string) { return this.devices.get(deviceHash)?.revokedAt === null; }

  private record(deviceHash: string, month: string): DeviceRecord {
    const device = this.devices.get(deviceHash)!;
    return { id: device.id, label: device.label, created_at: device.createdAt, revoked_at: device.revokedAt,
      proposals: this.requests.get(`${deviceHash}:${month}`) ?? 0, cellpose_fields: this.cellpose.get(`${deviceHash}:${month}`) ?? 0 };
  }

  async deviceStatus(deviceHash: string, month: string) {
    return (await this.deviceActive(deviceHash)) ? this.record(deviceHash, month) : null;
  }

  async listDevices(month: string) { return [...this.devices.keys()].map((hash) => this.record(hash, month)); }

  async revokeDevice(id: string, now: number) {
    const device = [...this.devices.values()].find((item) => item.id === id && item.revokedAt === null);
    if (!device) return false;
    device.revokedAt = now;
    return true;
  }

  async reserveCellpose(deviceHash: string, month: string, deviceLimit: number, totalLimit: number) {
    const key = `${deviceHash}:${month}`;
    const total = [...this.cellpose.entries()].filter(([item]) => item.endsWith(`:${month}`)).reduce((sum, [, value]) => sum + value, 0);
    if (total >= totalLimit || (this.cellpose.get(key) ?? 0) >= deviceLimit) return false;
    this.cellpose.set(key, (this.cellpose.get(key) ?? 0) + 1);
    return true;
  }

  async releaseCellpose(deviceHash: string, month: string) {
    const key = `${deviceHash}:${month}`;
    this.cellpose.set(key, Math.max(0, (this.cellpose.get(key) ?? 0) - 1));
  }

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
    if (this.blocked || this.reservations.has(id) || (this.spent.get(month) ?? 0) + held + amountUsd > budgetUsd) return false;
    this.reservations.set(id, { month, amount: amountUsd, createdAt: now });
    return true;
  }

  async unsettled(month: string) {
    return [...this.reservations.values()].filter((item) => item.month === month).reduce((sum, item) => sum + item.amount, 0);
  }

  async budgetBlocked() { return this.blocked; }

  async settle(id: string, month: string, spentUsd: number, usage?: UsageRecord, ceilingExceeded = false) {
    const reservation = this.reservations.get(id);
    if (reservation?.month !== month) return;
    if (ceilingExceeded || spentUsd > reservation.amount) this.blocked = true;
    if (usage) this.usage.set(id, usage);
    this.spent.set(month, (this.spent.get(month) ?? 0) + spentUsd);
    this.reservations.delete(id);
  }
}
