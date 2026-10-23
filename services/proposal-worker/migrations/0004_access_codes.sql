-- Access codes: an operator label per invitation/device, a public device id for
-- listing and revocation, and per-month Cellpose field counts. Rights and counts
-- only: no images, labels of research content or responses are stored.
ALTER TABLE invitations ADD COLUMN label TEXT;
ALTER TABLE devices ADD COLUMN id TEXT;
ALTER TABLE devices ADD COLUMN label TEXT;
-- Earlier devices get a listing id derived from their stored hash (not reversible).
UPDATE devices SET id = substr(hash, 1, 16) WHERE id IS NULL;
CREATE UNIQUE INDEX devices_id ON devices (id);
CREATE TABLE cellpose_usage (
  device TEXT NOT NULL,
  month TEXT NOT NULL,
  fields INTEGER NOT NULL CHECK (fields >= 0),
  PRIMARY KEY (device, month)
);
CREATE TABLE cellpose_months (
  month TEXT PRIMARY KEY,
  fields INTEGER NOT NULL CHECK (fields >= 0)
);
