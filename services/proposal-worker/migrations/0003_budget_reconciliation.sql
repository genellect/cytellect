-- A bound violation invalidates future reservations, even when the two-call hold
-- happens to cover this particular response. No research content is recorded.
ALTER TABLE settlements ADD COLUMN ceiling_exceeded INTEGER NOT NULL DEFAULT 0 CHECK (ceiling_exceeded IN (0, 1));
CREATE TABLE budget_incidents (
  settlement_id TEXT PRIMARY KEY REFERENCES settlements(id),
  reserved_usd REAL NOT NULL,
  accounted_usd REAL NOT NULL,
  reason TEXT NOT NULL CHECK (reason IN ('usage_ceiling_exceeded', 'reservation_exceeded')),
  resolved_at INTEGER,
  resolution_note TEXT
);
DROP TRIGGER settle_reservation;
CREATE TRIGGER settle_reservation AFTER INSERT ON settlements BEGIN
  INSERT INTO budget_incidents (settlement_id, reserved_usd, accounted_usd, reason)
    SELECT NEW.id, amount_usd, NEW.spent_usd,
      CASE WHEN NEW.ceiling_exceeded = 1 THEN 'usage_ceiling_exceeded' ELSE 'reservation_exceeded' END
    FROM reservations WHERE id = NEW.id AND month = NEW.month
      AND (NEW.ceiling_exceeded = 1 OR NEW.spent_usd > amount_usd);
  INSERT INTO usage_months (month, spent_usd) VALUES (NEW.month, NEW.spent_usd)
    ON CONFLICT (month) DO UPDATE SET spent_usd = spent_usd + excluded.spent_usd;
  DELETE FROM reservations WHERE id = NEW.id AND month = NEW.month;
END;
