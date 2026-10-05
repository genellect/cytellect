-- Opaque request rights and accounting only; no research content or response caching.
CREATE TABLE proposal_requests (
  device TEXT NOT NULL,
  request_id TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  PRIMARY KEY (device, request_id)
);
CREATE TABLE settlements (
  id TEXT PRIMARY KEY,
  month TEXT NOT NULL,
  spent_usd REAL NOT NULL CHECK (spent_usd >= 0),
  model TEXT,
  prompt_version TEXT,
  input_tokens INTEGER,
  cached_input_tokens INTEGER,
  output_tokens INTEGER,
  calls INTEGER
);
CREATE TRIGGER settle_reservation AFTER INSERT ON settlements BEGIN
  INSERT INTO usage_months (month, spent_usd) VALUES (NEW.month, NEW.spent_usd)
    ON CONFLICT (month) DO UPDATE SET spent_usd = spent_usd + excluded.spent_usd;
  DELETE FROM reservations WHERE id = NEW.id AND month = NEW.month;
END;
