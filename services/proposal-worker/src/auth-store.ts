/**
 * Accounts for cloud access. Only e-mail addresses, hashes of codes and tokens,
 * request/approval timestamps and usage counters are written here.
 */
import type { D1Database } from "./store";

export type UserState = "pending" | "allowed" | "revoked";
export type CodePurpose = "device" | "admin";

export interface UserRecord {
  email: string;
  state: UserState;
  gpu_seconds_month: number | null;
  proposal_usd_month: number | null;
  created_at: number;
  requested_at: number | null;
  notified_at: number | null;
  approved_at: number | null;
  revoked_at: number | null;
}

export interface CodeRecord { code_hash: string; sent_at: number; expires_at: number; attempts: number }

export interface DeviceRecord {
  email: string;
  state: UserState;
  gpu_seconds_month: number | null;
  proposal_usd_month: number | null;
  last_used_at: number;
  expires_at: number;
  revoked_at: number | null;
}

export interface Usage { gpu_seconds: number; proposal_usd: number }

export interface UserListing extends UserRecord { gpu_seconds: number; proposal_usd: number }

export class D1AuthStore {
  constructor(private readonly db: D1Database) {}

  user(email: string) {
    return this.db.prepare("SELECT * FROM users WHERE email = ?").bind(email).first<UserRecord>();
  }

  /** Records a request once; keeps the first request time and any existing state. */
  async requestAccess(email: string, now: number) {
    await this.db.prepare(
      "INSERT INTO users (email, state, created_at, requested_at) VALUES (?, 'pending', ?, ?) "
      + "ON CONFLICT (email) DO UPDATE SET requested_at = COALESCE(requested_at, excluded.requested_at)",
    ).bind(email, now, now).run();
    return (await this.user(email))!;
  }

  async markNotified(email: string, now: number) {
    await this.db.prepare("UPDATE users SET notified_at = ? WHERE email = ?").bind(now, email).run();
  }

  /** Pre-registers or approves. Returns the previous state (null when new). */
  async allow(email: string, now: number, onlyIfPending = false): Promise<UserState | null | false> {
    const previous = await this.user(email);
    if (onlyIfPending && previous?.state !== "pending") return false;
    await this.db.prepare(
      "INSERT INTO users (email, state, created_at, approved_at) VALUES (?, 'allowed', ?, ?) "
      + "ON CONFLICT (email) DO UPDATE SET state = 'allowed', approved_at = excluded.approved_at, revoked_at = NULL"
      + (onlyIfPending ? " WHERE state = 'pending'" : ""),
    ).bind(email, now, now).run();
    return previous?.state ?? null;
  }

  /**
   * Revokes the user, then every device of the user. The user state alone already
   * blocks all devices, so a failure between the two statements cannot leave access.
   */
  async revoke(email: string, now: number) {
    await this.db.prepare(
      "INSERT INTO users (email, state, created_at, revoked_at) VALUES (?, 'revoked', ?, ?) "
      + "ON CONFLICT (email) DO UPDATE SET state = 'revoked', revoked_at = excluded.revoked_at",
    ).bind(email, now, now).run();
    await this.db.prepare("UPDATE user_devices SET revoked_at = ? WHERE email = ? AND revoked_at IS NULL").bind(now, email).run();
  }

  async setLimits(email: string, gpuSeconds: number | null, proposalUsd: number | null) {
    const result = await this.db.prepare("UPDATE users SET gpu_seconds_month = ?, proposal_usd_month = ? WHERE email = ?")
      .bind(gpuSeconds, proposalUsd, email).run();
    return result.meta.changes === 1;
  }

  async listUsers(month: string) {
    const rows = await this.db.prepare(
      "SELECT u.*, COALESCE(g.gpu_seconds, 0) AS gpu_seconds, COALESCE(g.proposal_usd, 0) + "
      + "COALESCE((SELECT SUM(amount_usd) FROM reservations r WHERE r.user_email = u.email AND r.month = ?), 0) AS proposal_usd "
      + "FROM users u LEFT JOIN user_usage g ON g.email = u.email AND g.month = ? "
      + "ORDER BY CASE u.state WHEN 'pending' THEN 0 WHEN 'allowed' THEN 1 ELSE 2 END, u.email",
    ).bind(month, month).all<UserListing>();
    return rows.results;
  }

  async putCode(email: string, purpose: CodePurpose, hash: string, now: number, expiresAt: number) {
    await this.db.prepare(
      "INSERT INTO login_codes (email, purpose, code_hash, sent_at, expires_at, attempts) VALUES (?, ?, ?, ?, ?, 0) "
      + "ON CONFLICT (email, purpose) DO UPDATE SET code_hash = excluded.code_hash, sent_at = excluded.sent_at, "
      + "expires_at = excluded.expires_at, attempts = 0",
    ).bind(email, purpose, hash, now, expiresAt).run();
  }

  code(email: string, purpose: CodePurpose) {
    return this.db.prepare("SELECT code_hash, sent_at, expires_at, attempts FROM login_codes WHERE email = ? AND purpose = ?")
      .bind(email, purpose).first<CodeRecord>();
  }

  /** Counts one wrong attempt atomically; returns the new count, or null when already void. */
  async failAttempt(email: string, purpose: CodePurpose, max: number) {
    const row = await this.db.prepare(
      "UPDATE login_codes SET attempts = attempts + 1 WHERE email = ? AND purpose = ? AND attempts < ? RETURNING attempts",
    ).bind(email, purpose, max).first<{ attempts: number }>();
    return row?.attempts ?? null;
  }

  /** Consumes a matching, unexpired code exactly once. */
  async consumeCode(email: string, purpose: CodePurpose, hash: string, now: number, max: number) {
    const result = await this.db.prepare(
      "DELETE FROM login_codes WHERE email = ? AND purpose = ? AND code_hash = ? AND attempts < ? AND expires_at > ?",
    ).bind(email, purpose, hash, max, now).run();
    return result.meta.changes === 1;
  }

  async deleteCode(email: string, purpose: CodePurpose) {
    await this.db.prepare("DELETE FROM login_codes WHERE email = ? AND purpose = ?").bind(email, purpose).run();
  }

  async addDevice(hash: string, email: string, now: number, expiresAt: number) {
    await this.db.prepare("INSERT INTO user_devices (hash, email, created_at, last_used_at, expires_at) VALUES (?, ?, ?, ?, ?)")
      .bind(hash, email, now, now, expiresAt).run();
  }

  device(hash: string) {
    return this.db.prepare(
      "SELECT d.email, u.state, u.gpu_seconds_month, u.proposal_usd_month, d.last_used_at, d.expires_at, d.revoked_at "
      + "FROM user_devices d JOIN users u ON u.email = d.email WHERE d.hash = ?",
    ).bind(hash).first<DeviceRecord>();
  }

  async touchDevice(hash: string, now: number, expiresAt: number) {
    await this.db.prepare("UPDATE user_devices SET last_used_at = ?, expires_at = ? WHERE hash = ? AND revoked_at IS NULL")
      .bind(now, expiresAt, hash).run();
  }

  async removeDevice(hash: string) {
    await this.db.prepare("DELETE FROM user_devices WHERE hash = ?").bind(hash).run();
  }

  async addAdminSession(hash: string, email: string, expiresAt: number) {
    await this.db.prepare("INSERT INTO admin_sessions (hash, email, expires_at) VALUES (?, ?, ?)").bind(hash, email, expiresAt).run();
  }

  async adminSession(hash: string, now: number) {
    const row = await this.db.prepare("SELECT email FROM admin_sessions WHERE hash = ? AND expires_at > ?")
      .bind(hash, now).first<{ email: string }>();
    return row?.email ?? null;
  }

  async removeAdminSession(hash: string, now: number) {
    await this.db.prepare("DELETE FROM admin_sessions WHERE hash = ? OR expires_at <= ?").bind(hash, now).run();
  }

  async addApprovalLink(hash: string, email: string, expiresAt: number) {
    await this.db.prepare("INSERT INTO approval_links (hash, email, expires_at) VALUES (?, ?, ?)").bind(hash, email, expiresAt).run();
  }

  async approvalLinkUsable(hash: string, now: number) {
    return (await this.db.prepare("SELECT 1 AS ok FROM approval_links WHERE hash = ? AND used_at IS NULL AND expires_at > ?")
      .bind(hash, now).first()) !== null;
  }

  /** Marks the link used exactly once; returns its e-mail address. */
  async useApprovalLink(hash: string, now: number) {
    const row = await this.db.prepare(
      "UPDATE approval_links SET used_at = ? WHERE hash = ? AND used_at IS NULL AND expires_at > ? RETURNING email",
    ).bind(now, hash, now).first<{ email: string }>();
    return row?.email ?? null;
  }

  /**
   * Counter whose window starts at its first hit (one statement); returns the count
   * including this hit and when the window started.
   */
  async hit(key: string, now: number, window: number) {
    const row = await this.db.prepare(
      "INSERT INTO rate_limits (key, window_start, count) VALUES (?, ?, 1) ON CONFLICT (key) DO UPDATE SET "
      + "count = CASE WHEN window_start > ? THEN count + 1 ELSE 1 END, "
      + "window_start = CASE WHEN window_start > ? THEN window_start ELSE excluded.window_start END "
      + "RETURNING count, window_start",
    ).bind(key, now, now - window, now - window).first<{ count: number; window_start: number }>();
    return row ?? { count: Number.MAX_SAFE_INTEGER, window_start: now };
  }

  /** Starts (or restarts) a lock at `now`. */
  async lock(key: string, now: number) {
    await this.db.prepare(
      "INSERT INTO rate_limits (key, window_start, count) VALUES (?, ?, 1) "
      + "ON CONFLICT (key) DO UPDATE SET window_start = excluded.window_start, count = 1",
    ).bind(key, now).run();
  }

  /** Start of a lock still within `duration`, or null. */
  async lockedSince(key: string, now: number, duration: number) {
    const row = await this.db.prepare("SELECT window_start FROM rate_limits WHERE key = ? AND window_start > ?")
      .bind(key, now - duration).first<{ window_start: number }>();
    return row?.window_start ?? null;
  }

  async pruneRateLimits(before: number) {
    await this.db.prepare("DELETE FROM rate_limits WHERE window_start < ?").bind(before).run();
  }

  /** Settled GPU seconds and conservative proposal cost (settled plus outstanding holds). */
  async usage(email: string, month: string): Promise<Usage> {
    const row = await this.db.prepare(
      "SELECT COALESCE((SELECT gpu_seconds FROM user_usage WHERE email = ? AND month = ?), 0) AS gpu_seconds, "
      + "COALESCE((SELECT proposal_usd FROM user_usage WHERE email = ? AND month = ?), 0) + "
      + "COALESCE((SELECT SUM(amount_usd) FROM reservations WHERE user_email = ? AND month = ?), 0) AS proposal_usd",
    ).bind(email, month, email, month, email, month).first<Usage>();
    return row ?? { gpu_seconds: 0, proposal_usd: 0 };
  }

  /** Settled plus outstanding proposal cost for the whole service in the month. */
  async globalProposalUsd(month: string) {
    const row = await this.db.prepare(
      "SELECT COALESCE((SELECT spent_usd FROM usage_months WHERE month = ?), 0) + "
      + "COALESCE((SELECT SUM(amount_usd) FROM reservations WHERE month = ?), 0) AS usd",
    ).bind(month, month).first<{ usd: number }>();
    return row?.usd ?? 0;
  }

  async globalGpuSeconds(month: string) {
    const row = await this.db.prepare("SELECT COALESCE(SUM(gpu_seconds), 0) AS seconds FROM user_usage WHERE month = ?")
      .bind(month).first<{ seconds: number }>();
    return row?.seconds ?? 0;
  }

  /**
   * Admits one GPU request for the user in one statement: at most one in flight per
   * user (a slot older than `staleBefore` is taken over), remaining user time, and
   * remaining global time after holding `holdSeconds` for every other request in flight.
   */
  async acquireGpuSlot(email: string, month: string, now: number, staleBefore: number,
    userLimit: number, globalCap: number, holdSeconds: number): Promise<"ok" | "busy" | "user" | "global"> {
    const result = await this.db.prepare(
      "INSERT INTO gpu_slots (email, started_at) SELECT ?, ? WHERE "
      + "COALESCE((SELECT gpu_seconds FROM user_usage WHERE email = ? AND month = ?), 0) < ? AND "
      + "COALESCE((SELECT SUM(gpu_seconds) FROM user_usage WHERE month = ?), 0) + "
      + "? * (SELECT COUNT(*) FROM gpu_slots WHERE email <> ? AND started_at > ?) < ? "
      + "ON CONFLICT (email) DO UPDATE SET started_at = excluded.started_at WHERE gpu_slots.started_at <= ?",
    ).bind(email, now, email, month, userLimit, month, holdSeconds, email, staleBefore, globalCap, staleBefore).run();
    if (result.meta.changes === 1) return "ok";
    // Only selects the reason; admission itself was decided atomically above.
    if (await this.db.prepare("SELECT 1 AS ok FROM gpu_slots WHERE email = ? AND started_at > ?").bind(email, staleBefore).first()) return "busy";
    return (await this.usage(email, month)).gpu_seconds >= userLimit ? "user" : "global";
  }

  async releaseGpuSlot(email: string, startedAt: number) {
    await this.db.prepare("DELETE FROM gpu_slots WHERE email = ? AND started_at = ?").bind(email, startedAt).run();
  }

  async addGpuSeconds(email: string, month: string, seconds: number) {
    await this.db.prepare(
      "INSERT INTO user_usage (email, month, gpu_seconds, proposal_usd) VALUES (?, ?, ?, 0) "
      + "ON CONFLICT (email, month) DO UPDATE SET gpu_seconds = gpu_seconds + excluded.gpu_seconds",
    ).bind(email, month, seconds).run();
  }
}
