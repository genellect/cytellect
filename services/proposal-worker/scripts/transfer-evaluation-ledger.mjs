/** Move the existing approval; never mint another USD5 allowance. No API calls. */
import { lstatSync, realpathSync, existsSync, chmodSync, openSync, closeSync } from "node:fs";
import { dirname, basename, join, relative, isAbsolute, sep } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { DatabaseSync } from "node:sqlite";
import { EvaluationLedger } from "../src/evaluation-ledger.ts";

export const checkout = fileURLToPath(new URL("../../..", import.meta.url));

function external(filename, root, mustExist) {
  if (!isAbsolute(filename)) throw new Error("transfer_absolute_path_required");
  const target = join(realpathSync(dirname(filename)), basename(filename));
  const rel = relative(realpathSync(root), target);
  if (!rel || (rel !== ".." && !rel.startsWith(`..${sep}`) && !isAbsolute(rel))) throw new Error("transfer_outside_checkout_required");
  if (mustExist) {
    const stat = lstatSync(target);
    if (!stat.isFile() || stat.isSymbolicLink() || stat.nlink !== 1) throw new Error("transfer_regular_file_required");
  } else if (existsSync(target)) throw new Error("transfer_destination_exists");
  return target;
}

export async function exportLedger(source, destination, root = checkout) {
  source = external(source, root, true);
  destination = external(destination, root, false);
  const ledger = await EvaluationLedger.open(source, root, 5);
  const total = ledger.accountedUsd();
  ledger.close();
  const db = new DatabaseSync(source);
  try {
    db.exec("PRAGMA busy_timeout=5000; PRAGMA synchronous=FULL; BEGIN IMMEDIATE;");
    try {
      const config = db.prepare("SELECT blocked FROM approval WHERE id=1").get();
      if (config.blocked !== 0) throw new Error("transfer_source_blocked");
      db.exec("CREATE TABLE IF NOT EXISTS transfer (id INTEGER PRIMARY KEY CHECK(id=1), source_frozen INTEGER NOT NULL, activated INTEGER NOT NULL);");
      if (db.prepare("SELECT id FROM transfer WHERE id=1").get()) throw new Error("transfer_already_exported");
      // Mark the source ineligible for activation. Only the exported copy can
      // become the new active ledger after an explicit single-operator handoff.
      db.exec("INSERT INTO transfer VALUES (1,1,1); UPDATE approval SET blocked=1 WHERE id=1; COMMIT;");
    } catch (error) { db.exec("ROLLBACK;"); throw error; }
    // SQLite creates a coherent snapshot (including WAL) after new reservations
    // have been blocked. A failed export leaves the original frozen, fail closed.
    closeSync(openSync(destination, "wx", 0o600));
    db.prepare("VACUUM INTO ?").run(destination);
    chmodSync(destination, 0o600);
    const snapshot = new DatabaseSync(destination);
    try { snapshot.exec("PRAGMA synchronous=FULL; UPDATE transfer SET activated=0 WHERE id=1;"); }
    finally { snapshot.close(); }
    return { accounted_upper_usd: total, source_frozen: true, destination_blocked: true };
  } finally { db.close(); }
}

export async function activateLedger(destination, acknowledged, root = checkout) {
  if (acknowledged !== true) throw new Error("transfer_single_operator_ack_required");
  destination = external(destination, root, true);
  const ledger = await EvaluationLedger.open(destination, root, 5);
  const total = ledger.accountedUsd();
  ledger.close();
  const db = new DatabaseSync(destination);
  try {
    db.exec("PRAGMA busy_timeout=5000; PRAGMA synchronous=FULL; BEGIN IMMEDIATE;");
    try {
      const marker = db.prepare("SELECT source_frozen,activated FROM transfer WHERE id=1").get();
      const config = db.prepare("SELECT blocked FROM approval WHERE id=1").get();
      if (!marker || marker.source_frozen !== 1 || marker.activated !== 0 || config.blocked !== 1) throw new Error("transfer_snapshot_required");
      db.exec("UPDATE approval SET blocked=0 WHERE id=1; UPDATE transfer SET activated=1 WHERE id=1; COMMIT;");
      return { accounted_upper_usd: total, active_destination: true };
    } catch (error) { db.exec("ROLLBACK;"); throw error; }
  } finally { db.close(); }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    const [command, source, destination] = process.argv.slice(2);
    const result = command === "export" ? await exportLedger(source, destination)
      : command === "activate" ? await activateLedger(source, process.env.CYTELLECT_EVAL_SINGLE_OPERATOR === "true")
      : (() => { throw new Error("transfer_command_invalid"); })();
    console.info(JSON.stringify(result));
  } catch { console.error("evaluation_ledger_transfer_failed; keep original blocked and inspect operator instructions"); process.exitCode = 1; }
}
