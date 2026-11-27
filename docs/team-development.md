# チーム開発ルール / Team development rules

[日本語](#日本語) · [English](#english)

## 日本語

Cytellect の開発に参加するメンバーのためのルール。開発の進め方、Git の運用、研究データの扱いを定める。人も AI エージェントも守る原則は[開発の原則](development-principles.md)、開発環境の構築と起動は [CONTRIBUTING](../CONTRIBUTING.md) にある。AI エージェント向けの指示は [AGENTS.md](../AGENTS.md) にあり、この文書と同じ内容を前提にする。

### 1. 役割

| 役割 | 担当 | 責任 |
|---|---|---|
| プロダクトオーナー | `@genellect` | 優先順位、`main` へのマージ、本番公開と配布、外部サービスと費用の判断 |
| 開発メンバー | リポジトリの Collaborator | 担当タスクの実装、PR の作成、他のメンバーの PR のレビュー |
| AI エージェント | Claude Code、Codex など | 依頼者の指示による実装と検証。成果物の責任は依頼者が持つ |

### 2. 開発の流れ

1. **タスクを決める。** 目的と完了条件を Issue またはタスクの依頼に書く。
2. **ブランチを作る。** 最新の `origin/main` から作る。名前は `<種類>/<内容>` とする（例: `fix/nucleolus-boundary`）。種類は `feat`、`fix`、`docs`、`test`、`chore`、`ci` のいずれかで、内容は英小文字とハイフンで短く書く。日付や非公開の研究対象は名前に入れない。`release/`、`feature/`、`review/` と、種類のない名前は使わない。エージェントのツールがブランチ名を自動で決める場合に限り、その接頭辞（`claude/`、`codex/`）のままでよい。
3. **変更する。** 1 つの PR では 1 つの目的だけを扱う。仕様・テスト・文書は、コードと同じ PR で更新する。
4. **PR を出す。** [PR テンプレート](../.github/pull_request_template.md)のすべての項目を書く。作業途中の共有には Draft PR を使う。
5. **CI とレビューを通す。** 必須 CI がすべて成功し、必要なレビューを得るまでマージしない。PR の CI は、変更したファイルに関係する検査だけを実行する。Fiji・Cellpose の画像・Windows の導入の統合試験は `main` への取り込み後に実行し、Windows 版の配布は、配布するコミットでこれらすべての成功を確認してから行う（[CI の構成](ci.md)）。`main` で失敗した場合は、次の配布より前に修正するか取り消す。
6. **マージする。** オーナーが squash merge で `main` に取り込む。PR のタイトルがそのままコミットの件名になるため、変更の内容が分かるタイトルにする。`main` はルールセットで更新を制限しており、PR をマージできるのはバイパス権限を持つオーナーだけ。マージの前に最新の `main` を取り込み、その head で必須 CI がすべて成功したことを確かめる。オーナーはマージ画面でルールのバイパスを選ぶか、`gh pr merge <番号> --squash --admin --match-head-commit <確かめた SHA>` を実行する。GraphQL を使えない Claude Code のクラウドセッションでは、同じ操作を REST で行う：`gh api -X PUT repos/genellect/cytellect/pulls/<番号>/merge -f merge_method=squash -f sha=<確かめた SHA>`。CI の結果は `gh api repos/genellect/cytellect/commits/<SHA>/check-runs` で確かめる。バイパスは必須 CI の条件も飛ばすため、成功を確かめずに実行しない。

### 3. Git の運用

- `main` への直接 push、force push、ブランチ保護の変更をしない。
- 作業を始める前と PR を出す前に `git fetch origin main` を実行し、最新の `main` を取り込む。取り込み後は、影響する検証をやり直す。
- 他のメンバーのブランチには、本人の了承なく push しない。
- 並行作業では、タスクごとに `git worktree` または別の checkout を使う。他の人やエージェントが使用中の checkout は編集しない。
- マージ済みのブランチは削除する。オーナーはリポジトリ設定の **Automatically delete head branches** を有効にしておき、マージと同時に削除されるようにする。
- マージせずに閉じた PR のブランチも削除する。コミットは PR に残り、PR の画面からブランチを復元できる。残したい案は Issue に記録する。
- PR のないブランチは残さない。作業を共有するときは Draft PR を出す。
- 配布した版はタグと GitHub Releases で示し、版ごとのブランチは作らない。タグとリリースは配布の workflow が `main` のコミットに作る（[配布する](release-signing.md#4-配布する)）。

### 4. レビュー

- オーナー以外が作成した PR には、作成者とは別のメンバー 1 名以上の承認が要る。
- オーナー自身の PR は、レビューを省略できる。PR と必須 CI は省略できない。
- エージェントが作成した変更は、作業を依頼した人の変更として扱う。オーナーのアカウントで動くエージェントが他のメンバーの依頼で作成した変更にも、レビューが要る。
- レビューで最も重視するのは次の 2 点である。
  1. 変更が目的に合い、合理的で、無関係な修正を含まないか
  2. 本番への影響（公開サイト、Windows 版、Docker 版、AI サービス）と、画素値・マスク・測定値・統計・図への影響が検証されているか
- あわせて次の点を確認する。
  - 原因が証拠で特定され、個別の対症ではなく一般則や構造で対処しているか（[問題への対処](development-principles.md#問題への対処)）
  - 非公開データや認証情報が含まれていないか
  - 検証の結果が事実どおりに書かれ、未実施の項目が明示されているか

### 5. AI エージェントの利用

- エージェントへの依頼は、目的、対象範囲、完了条件を明確にする。
- 並行して動かすエージェントには、別々のブランチと worktree を割り当て、同じファイルを編集させない。
- エージェントの成果物は、依頼者が内容を確認してからレビューに出す。
- エージェントが作成したコミットには、ツールが付ける `Co-Authored-By` 行を残す。
- エージェントにマージをさせるのは、オーナーがその PR について明示的に指示した場合に限る。マージの許可は、マージした内容の本番デプロイと本番配布の許可を兼ねる（[7](#7-本番公開と配布)）。
- 作業の引き継ぎは、PR の説明と [roadmap](roadmap.md) に記録する。セッションごとの引き継ぎ文書は新たに作らない。

### 6. 研究データの扱い

研究データは、次の区分で管理する。

| 区分 | 例 | 保存場所 | Git・CI・開発用 AI |
|---|---|---|---|
| 非公開データ | 研究室の未発表画像、正解の輪郭、測定表、論文草稿、ファイル名とパス、参加者情報 | 研究室が管理するストレージ（checkout の外） | 使用不可（開発用 AI は下の隔離ローカル環境の例外だけ） |
| 公開データ | 出典とライセンスを確認した公開画像 | 登録済みの fixture。出典、染色情報、再配布条件、ハッシュを記録 | 使用可（リポジトリに置くのは再配布できるものだけ） |
| 合成データ | 計算の照合に使う最小の数値・ラベルの配列（細胞を模した画像は除く） | リポジトリ | [開発の原則](development-principles.md#研究データと検証)の条件を満たす場合に限り使用可 |
| 認証情報 | API キー、トークン、招待リンク | 各サービスの secret 管理 | 使用不可 |

- 非公開データは、コード、ログ、Issue、PR、スクリーンショット、CI、開発用 AI（チャットへの貼り付けを含む）に含めない。開発用 AI の例外は、次の隔離ローカル環境だけ。
- **隔離ローカル環境の例外。** オーナーが指定した隔離ローカル領域で、オーナーが指定した開発用 AI とそのモデル提供元に限り、指定した目的のために非公開データを扱ってよい（2026-11-09、オーナーの判断）。領域・AI と送信先・目的と条件は[ローカル研究データの利用](drafts/research-measurements/local-data.md#隔離ローカル環境での-ai-の利用)に従い、その外（クラウド開発、Git、PR、CI、公開デモ、ほかの AI）には適用しない。
- プロダクトの解析支援（解析提案と考察）は、利用者の同意のもとで、[定められた研究データ](../SECURITY.md#51-pc-の外部へ送信する情報)（目的、チャネル名、視野の名前と記録、視野を追加したときに選んだフォルダーの名前と、その中のフォルダー名・ファイル名、実験回と群の名前、代表的な視野の縮小画像、保存した結果）を LLM に示す。この機能は、開発で非公開データを扱ってよい根拠にはならない。
- **評価データを分ける。** 検出精度の評価には、学習と条件調整に使わない実験回の画像を使う。分割は実験回の単位で行い、どの画像をどちらに使ったかを記録する。評価データを見て閾値やモデルを調整しない。
- **学習済みモデルを管理する。** 非公開データで学習した重みを公開・配布する場合は、オーナーとデータ提供元の承認を得る。学習データ、重み、推論条件は組にして版を管理する。
- **共同研究先のデータ。** 提供元との取り決め（利用目的、保存場所、保存期間）の範囲内で使う。
- **結果の公開。** 非公開データによる検証結果は、オーナーが承認した匿名化済みの集計だけを公開する。
- **誤って含めた場合。** 非公開データや認証情報をコミット・送信した場合は、すぐにオーナーへ連絡する。追加のコミットで削除しても履歴には残るため、単独で履歴を書き換えずに対応を相談する。認証情報は直ちに無効化して再発行する。

### 7. 本番公開と配布

- **`main` へのマージの許可は、マージした内容のすべての本番デプロイと本番配布の許可を兼ねる**（2026-11-27、オーナーの判断）。対象は、公開サイト（Vercel）、公開デモの作り直し、AI の中継 Worker、Cellpose の GPU サーバー（Modal）とそのイメージ、Docker 版、Windows 版の EXE と Microsoft Store への提出。マージのあとに、デプロイや配布ごとの承認を求めない。EXE の自動配布（[#261](https://github.com/genellect/cytellect/issues/261)、[#263](https://github.com/genellect/cytellect/pull/263)）で仕組みにした方針を、すべての経路に当てはめる。
- **自動の経路は、マージからそのまま進む。** Vercel は本番サイトをデプロイする。EXE の[自動配布](release-signing.md#exe-の自動配布)と [Microsoft Store への提出](windows-msix.md#main-から提出する)は、`main` で CI に成功した最も新しいコミットだけを対象にし、CI に失敗したコミットは配布しない。承認に代わる安全策は、マージの前のレビューと必須 CI、`main` での CI と配布試験にある。
- **手で行う手順が残る経路も、`main` にマージした版については承認済み。** 中継 Worker、Modal、公開デモの作り直しなどは、各文書の手順と検証に従って行い、前後の版を記録する。EXE の[手動配布](release-signing.md#手動配布)は、版や対象のコミットを指定してオーナー自身が起動する経路で、起動したオーナーが `release` 環境で確かめる。マージした版の配布は自動配布が行うので、これはマージの後に求める承認ではない。
- **次は、マージの許可に含まれない。** オーナーが対象を指示する：`main` へのマージそのもの、`main` にマージしていない内容（PR の head など）の本番へのデプロイ・配布、ロールバック、有料サービスの利用（有料 API での評価など）、有料サービスの契約、外部サービスの追加、費用が発生する設定。
- Windows 版の配布には、配布物の導入後の受入確認を要する。

### 8. このルールの変更

変更は PR で提案し、オーナーの承認を得る。日本語と英語は同じ PR で更新し、[AGENTS.md](../AGENTS.md) と内容を一致させる。

文書間の矛盾を見つけた場合は、いずれかの誤りとして扱い、自分の判断で直さない。コード・設定・記録と事実を照合したうえで、ただちにオーナーに確認する。

## English

These rules apply to everyone contributing to Cytellect. They define how we work, how we use Git and how we handle research data. The principles that people and AI agents follow are in [Development principles](development-principles.md) (Japanese), and setting up a development environment is covered in [CONTRIBUTING](../CONTRIBUTING.md) (Japanese). Instructions for AI agents are in [AGENTS.md](../AGENTS.md) and are consistent with this document.

### 1. Roles

| Role | Who | Responsibilities |
|---|---|---|
| Product owner | `@genellect` | Priorities, merges into `main`, production release and distribution, external services and spending |
| Developer | Repository collaborators | Implementing assigned tasks, opening PRs, reviewing other members' PRs |
| AI agent | Claude Code, Codex and similar tools | Implementation and validation on a requester's instruction; the requester is accountable for the output |

### 2. Workflow

1. **Define the task.** State the purpose and completion criteria in an issue or task request.
2. **Create a branch** from the latest `origin/main`, named `<type>/<summary>` (for example `fix/nucleolus-boundary`). The type is one of `feat`, `fix`, `docs`, `test`, `chore` or `ci`, and the summary is short, in lowercase English words joined by hyphens. Do not put dates or unpublished research targets in the name. Do not use `release/`, `feature/`, `review/` or names without a type. Only when an agent tool chooses the branch name itself may its prefix (`claude/`, `codex/`) remain.
3. **Make the change.** Keep each PR to one purpose. Update specifications, tests and documentation in the same PR as the code.
4. **Open a PR** and fill in every section of the [PR template](../.github/pull_request_template.md) (Japanese). Use a draft PR to share work in progress.
5. **Pass CI and review.** Do not merge until all required checks pass and the required review is complete. Pull-request CI runs only the checks the changed files can affect. The Fiji, Cellpose-image and Windows-install integration jobs run after merge on `main`, and a Windows release proceeds only when all of them have passed on the commit it releases ([CI design](ci.md)). A failure on `main` is fixed or reverted before the next release.
6. **Merge.** The owner squash-merges into `main`. The PR title becomes the commit subject, so make it describe the change. A ruleset restricts updates to `main`, so only the owner, who holds bypass permission, can merge PRs. Before merging, integrate current `main` and confirm that every required check passed on that head. The owner then selects the rule bypass on the merge screen or runs `gh pr merge <number> --squash --admin --match-head-commit <verified SHA>`. Claude Code cloud sessions cannot use GraphQL, so they do the same through REST: `gh api -X PUT repos/genellect/cytellect/pulls/<number>/merge -f merge_method=squash -f sha=<verified SHA>`, after checking `gh api repos/genellect/cytellect/commits/<SHA>/check-runs`. The bypass also skips the required-check condition, so never use it before confirming success.

### 3. Git

- Do not push directly to `main`, force-push, or change branch protection.
- Run `git fetch origin main` and integrate current `main` before starting work and before opening a PR. Rerun affected checks after integrating.
- Do not push to another member's branch without their agreement.
- For parallel work, use a separate `git worktree` or checkout per task. Do not edit a checkout that another person or agent is using.
- Delete branches after they are merged. The owner keeps the repository setting **Automatically delete head branches** enabled so that merging deletes the branch.
- Also delete the branch of a PR closed without merging. Its commits stay with the PR, and the branch can be restored from the PR page. Record any idea worth keeping in an issue.
- Do not keep branches without a PR. Open a draft PR to share work in progress.
- Mark released versions with tags and GitHub Releases, not per-version branches. The release workflow creates the tag and release on a `main` commit ([Release](release-signing.md#4-配布する)).

### 4. Review

- PRs authored by anyone other than the owner require approval from at least one member other than the author.
- The owner's own PRs may omit review. They still require a PR and all required checks.
- A change made by an agent belongs to the person who requested it. An agent running under the owner's account on another member's behalf still requires review.
- Review focuses first on two points:
  1. the change matches its purpose, is reasonable and contains no unrelated edits;
  2. its effects on production (public site, Windows release, Docker release, AI services) and on pixel values, masks, measurements, statistics and figures are tested.
- Reviewers also check that:
  - causes are identified from evidence and fixed through general rules or structure rather than case-specific patches ([Development principles](development-principles.md#問題への対処), Japanese);
  - no private data or credentials are included;
  - validation results are reported accurately and unrun checks are stated.

### 5. Working with AI agents

- Give agents a clear purpose, scope and completion criteria.
- Assign each concurrent agent its own branch and worktree, and do not let two agents edit the same files.
- The requester reviews an agent's output before requesting review from others.
- Keep the `Co-Authored-By` lines that agent tools add to commits.
- Agents merge only when the owner explicitly instructs them to for that PR. Permission to merge also covers the production deployment and distribution of the merged content ([7](#7-production-release-and-distribution)).
- Record handoffs in the PR description and the [roadmap](roadmap.md). Do not create new per-session handoff documents.

### 6. Research data

Research data falls into these categories.

| Category | Examples | Storage | Git, CI and development AI |
|---|---|---|---|
| Private data | Unpublished lab images, ground-truth contours, measurement tables, manuscript drafts, file names and paths, participant information | Lab-managed storage outside the checkout | Not permitted (development AI only under the isolated local environment exception below) |
| Public data | Published images with confirmed source and license | Registered fixtures with recorded source, stain metadata, redistribution terms and hashes | Permitted (only redistributable assets in the repository) |
| Synthetic data | Minimal numeric or label arrays for checking calculations (not images imitating cells) | Repository | Permitted only under the conditions in [Development principles](development-principles.md#研究データと検証) |
| Credentials | API keys, tokens, invitation links | Each service's secret store | Not permitted |

- Keep private data out of code, logs, issues, PRs, screenshots, CI and development AI, including pasting into chat. The only exception for development AI is the isolated local environment below.
- **Isolated local environment exception.** Only in an isolated local area the owner designates, and only the development AI the owner designates together with its model provider, may handle private data, and only for the designated purposes (owner's decision, 2026-11-09). The area, AI and recipient, purposes and conditions are in [Local research data](drafts/research-measurements/local-data.md#隔離ローカル環境での-ai-の利用); the exception never extends to cloud development, Git, PRs, CI, public demos or other AI.
- The product's analysis assistance (proposals and discussions) shows the LLM the [defined research data](../SECURITY.en.md#51-information-transmitted-from-the-pc) (the goal, channel labels, field names and records, the name of the folder chosen when files were added and the folder and file names inside it, run and group names, display-scaled previews of a representative field, saved results) with the user's consent. It does not permit handling private data during development.
- **Separate evaluation data.** Evaluate detection accuracy on images from experimental runs that were not used for training or parameter tuning. Split by experimental run and record which images were used for which purpose. Do not tune thresholds or models against evaluation data.
- **Manage trained models.** Publishing or distributing weights trained on private data requires approval from the owner and the data provider. Version training data, weights and inference settings together.
- **Collaborator data.** Use data from partner labs only within the agreed purpose, storage location and retention period.
- **Publishing results.** Publish results from private-data validation only as anonymized aggregates approved by the owner.
- **Accidental exposure.** If private data or credentials are committed or sent, notify the owner immediately. A follow-up commit does not remove them from history, so agree on the remedy instead of rewriting history alone. Revoke and reissue exposed credentials at once.

### 7. Production release and distribution

- **Permission to merge into `main` is also permission for every production deployment and distribution of the merged content** (owner's decision, 2026-11-27). This covers the public site (Vercel), rebuilding the public demo, the AI relay Worker, the Cellpose GPU server (Modal) and its image, the Docker version, the Windows EXE and the Microsoft Store submission. No deployment or distribution asks for another approval after the merge. The policy built into automatic EXE distribution ([#261](https://github.com/genellect/cytellect/issues/261), [#263](https://github.com/genellect/cytellect/pull/263)) applies to every route.
- **Automatic routes proceed from the merge.** Vercel deploys the production site. [Automatic EXE distribution](release-signing.md#exe-の自動配布) and the [Microsoft Store submission](windows-msix.md#main-から提出する) take only the newest `main` commit that passed CI, and never a commit that failed CI. The safeguards that replace an approval are review and required CI before the merge, and CI and distribution tests on `main`.
- **Routes with manual steps are approved as well for the version merged into `main`.** The relay Worker, Modal and rebuilding the public demo follow the procedure and checks of their documents, and record the versions before and after. [Manual EXE distribution](release-signing.md#手動配布) is a route the owner starts with a chosen version or commit, and the owner who started it confirms it in the `release` environment. Automatic distribution already distributes the merged version, so this is not an approval asked for after the merge.
- **Permission to merge does not cover the following.** The owner names the target: the merge into `main` itself, deploying or distributing content that is not merged into `main` (such as a PR head) to production, rollbacks, use of paid services (such as evaluation through a paid API), paid subscriptions, new external services and settings that incur costs.
- Windows distribution requires installed-copy acceptance.

### 8. Changing these rules

Propose changes in a PR and obtain the owner's approval. Update the Japanese and English sections in the same PR and keep [AGENTS.md](../AGENTS.md) consistent.

If you find a contradiction between documents, treat one of them as wrong and do not fix it on your own. Check the facts against the code, settings and records, then ask the owner immediately.
