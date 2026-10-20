@AGENTS.md

# Working with Claude

## 日本語

変更前に [AGENTS.md](AGENTS.md) とこのファイルを必ず読んでください。目的と開発ルールは `AGENTS.md` に集約しています。日本語全文の後に、同じ内容の英語全文を置いています。

作業は最新 main を取り込んだ専用 worktree・feature ブランチで行い、PR を作成します。main のマージと本番公開には、それぞれ `genellect` 本人の明示的指示が必要です。

Claude のクラウド環境は [.claude/cloud-setup.sh](.claude/cloud-setup.sh) を使います。[以前の引き継ぎ](docs/claude-code-handoff.md)と [2026-10-06 の記録](docs/claude-handoff-2026-10-06.md)は、過去の経緯を調べるときに参照してください。記載されたブランチへの復帰や公開を、新しい作業で自動的に実行してはいけません。

## English

Before any change, read [AGENTS.md](AGENTS.md) and this file. `AGENTS.md` is the shared source for product direction and development rules, with the complete Japanese text followed by the equivalent English text.

Work in a dedicated worktree and feature branch that incorporates current main, then open a PR. Merging into main and publishing to production each require an explicit instruction from `genellect`.

For Claude's cloud environment, use [.claude/cloud-setup.sh](.claude/cloud-setup.sh). Consult the [earlier handoff](docs/claude-code-handoff.md) and [2026-10-06 record](docs/claude-handoff-2026-10-06.md) when historical context is needed. Do not automatically resume their branches or repeat their release actions for new work.
