-- Rights and usage only: no images, goals, prompts or model outputs.
CREATE TABLE invitations (
  hash TEXT PRIMARY KEY,
  expires_at INTEGER NOT NULL,
  redeemed_at INTEGER
);
CREATE TABLE devices (
  hash TEXT PRIMARY KEY,
  created_at INTEGER NOT NULL,
  revoked_at INTEGER
);
CREATE TABLE device_usage (
  device TEXT NOT NULL,
  month TEXT NOT NULL,
  requests INTEGER NOT NULL,
  PRIMARY KEY (device, month)
);
CREATE TABLE usage_months (
  month TEXT PRIMARY KEY,
  spent_usd REAL NOT NULL
);
CREATE TABLE reservations (
  id TEXT PRIMARY KEY,
  month TEXT NOT NULL,
  amount_usd REAL NOT NULL,
  created_at INTEGER NOT NULL
);
CREATE INDEX reservations_month ON reservations (month, created_at);
