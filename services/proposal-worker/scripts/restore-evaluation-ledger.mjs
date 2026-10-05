/** Restore an operator-supplied accounting snapshot outside Git, without keys. */
import { createHash } from "node:crypto";
import { writeFileSync, realpathSync } from "node:fs";
import { isAbsolute, dirname, basename, relative, join, sep } from "node:path";
import { pathToFileURL } from "node:url";
import { checkout, activateLedger } from "./transfer-evaluation-ledger.mjs";

export async function restoreLedger(env, root = checkout) {
  if (env.CLAUDE_CODE_REMOTE !== "true" || env.CYTELLECT_EVAL_SINGLE_OPERATOR !== "true") throw new Error("restore_operator_ack_required");
  const encoded = env.CYTELLECT_EVAL_LEDGER_SNAPSHOT_B64;
  const digest = env.CYTELLECT_EVAL_LEDGER_SHA256;
  const filename = env.CYTELLECT_PUBLIC_EVAL_LEDGER;
  if (typeof encoded !== "string" || encoded.length > 400_000 || !/^[A-Za-z0-9+/]+={0,2}$/.test(encoded)
    || typeof digest !== "string" || !/^[a-f0-9]{64}$/.test(digest) || !isAbsolute(filename ?? "")) throw new Error("restore_snapshot_invalid");
  const data = Buffer.from(encoded, "base64");
  if (data.length < 512 || data.length > 256_000 || data.subarray(0, 16).toString() !== "SQLite format 3\0"
    || createHash("sha256").update(data).digest("hex") !== digest) throw new Error("restore_snapshot_invalid");
  const target = join(realpathSync(dirname(filename)), basename(filename));
  const rel = relative(realpathSync(root), target);
  if (!rel || (rel !== ".." && !rel.startsWith(`..${sep}`) && !isAbsolute(rel))) throw new Error("restore_outside_checkout_required");
  // Exclusive creation rejects symlinks/existing ledgers. The hash detects transfer
  // corruption, not a malicious operator: keep the snapshot and digest private.
  writeFileSync(target, data, { flag: "wx", mode: 0o600 });
  return activateLedger(target, true, root);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try { console.info(JSON.stringify(await restoreLedger(process.env))); }
  catch { console.error("evaluation_ledger_restore_failed; never initialize a replacement allowance"); process.exitCode = 1; }
}
