-- Cloud access: e-mail login codes, owner approval, user-bound device tokens and
-- per-user monthly usage. Only e-mail addresses, hashes of codes and tokens,
-- request/approval timestamps and usage counters are stored: no images, goals,
-- prompts, outputs or device names.
CREATE TABLE users (
  email TEXT PRIMARY KEY,
  state TEXT NOT NULL CHECK (state IN ('pending', 'allowed', 'revoked')),
  -- NULL means the Worker's default monthly limit applies.
  gpu_seconds_month INTEGER CHECK (gpu_seconds_month IS NULL OR gpu_seconds_month >= 0),
  proposal_usd_month REAL CHECK (proposal_usd_month IS NULL OR proposal_usd_month >= 0),
  created_at INTEGER NOT NULL,
  requested_at INTEGER,
  notified_at INTEGER,
  approved_at INTEGER,
  revoked_at INTEGER
);
CREATE TABLE login_codes (
  email TEXT NOT NULL,
  purpose TEXT NOT NULL CHECK (purpose IN ('device', 'admin')),
  code_hash TEXT NOT NULL,
  sent_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (email, purpose)
);
CREATE TABLE user_devices (
  hash TEXT PRIMARY KEY,
  email TEXT NOT NULL REFERENCES users (email),
  created_at INTEGER NOT NULL,
  last_used_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL,
  revoked_at INTEGER
);
CREATE INDEX user_devices_email ON user_devices (email);
CREATE TABLE admin_sessions (
  hash TEXT PRIMARY KEY,
  email TEXT NOT NULL,
  expires_at INTEGER NOT NULL
);
CREATE TABLE approval_links (
  hash TEXT PRIMARY KEY,
  email TEXT NOT NULL,
  expires_at INTEGER NOT NULL,
  used_at INTEGER
);
-- Lets the requesting PC learn the state of its own access request, without the
-- address in a URL and without revealing other addresses' states.
CREATE TABLE request_tokens (
  hash TEXT PRIMARY KEY,
  email TEXT NOT NULL,
  expires_at INTEGER NOT NULL
);
-- Keys are keyed hashes of the e-mail address or client IP, never the raw value.
CREATE TABLE rate_limits (
  key TEXT PRIMARY KEY,
  window_start INTEGER NOT NULL,
  count INTEGER NOT NULL
);
CREATE TABLE user_usage (
  email TEXT NOT NULL,
  month TEXT NOT NULL,
  gpu_seconds INTEGER NOT NULL DEFAULT 0 CHECK (gpu_seconds >= 0),
  proposal_usd REAL NOT NULL DEFAULT 0 CHECK (proposal_usd >= 0),
  PRIMARY KEY (email, month)
);
-- At most one GPU request (inference or health check) in flight per user. A slot
-- holds `hold_seconds` against the global cap while expires_at is in the future.
CREATE TABLE gpu_slots (
  email TEXT PRIMARY KEY,
  kind TEXT NOT NULL CHECK (kind IN ('inference', 'health')),
  hold_seconds INTEGER NOT NULL CHECK (hold_seconds > 0),
  started_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL
);
-- Proposal reservations made with a user-bound token also count against that user.
ALTER TABLE reservations ADD COLUMN user_email TEXT;
ALTER TABLE settlements ADD COLUMN user_email TEXT;
CREATE INDEX reservations_user ON reservations (user_email, month);
DROP TRIGGER settle_reservation;
CREATE TRIGGER settle_reservation AFTER INSERT ON settlements BEGIN
  INSERT INTO budget_incidents (settlement_id, reserved_usd, accounted_usd, reason)
    SELECT NEW.id, amount_usd, NEW.spent_usd,
      CASE WHEN NEW.ceiling_exceeded = 1 THEN 'usage_ceiling_exceeded' ELSE 'reservation_exceeded' END
    FROM reservations WHERE id = NEW.id AND month = NEW.month
      AND (NEW.ceiling_exceeded = 1 OR NEW.spent_usd > amount_usd);
  INSERT INTO usage_months (month, spent_usd) VALUES (NEW.month, NEW.spent_usd)
    ON CONFLICT (month) DO UPDATE SET spent_usd = spent_usd + excluded.spent_usd;
  INSERT INTO user_usage (email, month, gpu_seconds, proposal_usd)
    SELECT NEW.user_email, NEW.month, 0, NEW.spent_usd WHERE NEW.user_email IS NOT NULL
    ON CONFLICT (email, month) DO UPDATE SET proposal_usd = proposal_usd + excluded.proposal_usd;
  DELETE FROM reservations WHERE id = NEW.id AND month = NEW.month;
END;
