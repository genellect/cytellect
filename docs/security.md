# Protection and operations

**This checkpoint is not safe to deploy with research data.** Authorization is draft code; cleanup, supervision and security tests are absent.

Public source/synthetic fixtures can enter GitHub/Cloud/CI. Research images/PDFs, filenames, paths, conditions/results, previews/masks/tables/figures, tokens/secrets cannot. Real validation occurs in a separate approved private environment.

Runtime files stay on a private volume outside checkout. Browser uploads directly to API with TLS; CDN serves UI only. Ownership on every route, no-store on research responses. No analytics/recording/LLM transmission. IDs are not permissions.

One-use expiring invite exchanged for Secure HttpOnly session, hashes server-side, no query/localStorage secrets; exact CORS, Origin/CSRF and revocation. Logs exclude payloads/filenames/conditions/tokens.

24h retention from explicit operation; polling excluded. Expiry/deletion immediately blocks access, then stops execution and deletes files safely. Reject stale/deleted-workspace worker results. Test interruption/restart/races before PoC. No general research-file backups.

Allowlisted recipes, bounded memory/time, no worker egress or arbitrary code/macros/URLs. Freeze dependencies/weights at build. Validate decompressed dimensions/axes/count/bytes.

Do not attach research data or credentials to issues. Configure and verify private vulnerability reporting before external PoC; no active reporting channel is claimed now.
