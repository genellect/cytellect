# CI の構成

PR と `main` で実行される CI のジョブと、その選ばれ方をまとめる。手元では `python3 scripts/dev.py check` で、PR の `python` ジョブと `web` ジョブと同じ検査を実行できる（[CONTRIBUTING](../CONTRIBUTING.md)）。

## PR で実行されるジョブ

PR では、変更したファイルが影響しうるジョブだけを実行する。どのファイルがどの領域に当たるかは、`scripts/ci_changes.py` が決める。

| 領域 | 主な内容 | 選ばれる変更 |
|---|---|---|
| `python` | Ruff、mypy、Linux でのテスト一式、解析計画と解析提案の検査、依存パッケージの監査と SBOM | 解析、API、ワーカー、`scripts`、`tests`、`engines`、`infra` |
| `web` | API 契約の再生成、Next.js の検査とビルド、解析提案の Worker、公開サイトのブラウザ試験 | `apps/web`、契約、解析提案の Worker、解析・API・ワーカー |
| `lp` | Next.js の検査とビルド、LP のブラウザ試験 | LP の部品・素材・試験だけ。`web` が選ばれたときは実行しない |
| `fiji` | 実際の Fiji、API とブラウザの連携、コンテナ、ローカル版の Web | `apps/web`、契約、解析・API・ワーカー、`scripts`、`tests`、Fiji、`infra` |
| `windows` | Windows のセットアップとランチャーの試験、Python 3.14 でのテスト一式 | 解析・API・ワーカー、`scripts`、`tests`、`engines`、ローカル版の書き出し |

**LP だけの変更**：LP の部品（`PublicLanding`、`Landing*`、`HeroFilm`、`optical-landing.module.css`）、`lp-metrics`、LP のブラウザ試験（`marketing`、`lp-*`）は `lp` だけを選ぶ。LP の素材（`apps/web/public/marketing/**`）と `fixtures/public/allowlist.json` は Windows 版の配布物にも含まれるため、`python` と `lp` を選ぶ。`lp` は API 契約の再生成、解析提案の Worker、デモのブラウザ試験、依存の記録を省き、pnpm のストアと試験用のブラウザをキャッシュから復元する。`web` も同じ LP の試験を実行するため、`web` が選ばれたとき（`main` への push を含む）は `lp` を実行しない。ヒーロー映像の制作用スクリプト（`scripts/lp_film/**`）は、どの領域も選ばない。

**文書だけの変更**：`docs/**`、ルートの Markdown、`.github/` 配下の Markdown（PR・Issue のテンプレート）、`LICENSE`、`NOTICE` は、どの領域も選ばない。`fixtures/public/allowlist.json` の変更が `docs/` の画像の登録だけの場合も、文書の変更として扱い、どの領域も選ばない。

**すべての領域を選ぶ変更**：workflow、lockfile、パッケージの定義、`fixtures/` のその他のファイル、規則にないパス。トップレベルのディレクトリを追加するときは、`scripts/ci_changes.py` の規則とその試験も更新する。

公開ツリーの検査、文書のリンク検査、全履歴のシークレット走査は、どの変更でも実行する。Python のテスト一式が選ばれないときは、配布物に含める文書の試験を実行する。実行しなかったジョブは、ブランチ保護には成功として報告される。

図の描画に使う日本語フォント（`fonts-noto-cjk`、約 61 MB）は、Linux のジョブで `scripts/install_figure_font.sh` が導入する。遅いミラーが取得に 20 分以上かかり、`python` ジョブが試験の途中で 30 分の上限に達したことがあるため、取得が 20 秒続けて遅いミラーは打ち切り、別の公式ミラーで続きから取得する。導入するのは、apt の署名済みの索引にある SHA-256 と一致したファイルだけで、どのミラーからでも同じパッケージになる。

## main で実行される統合試験

`fiji-browser`（実際の Fiji、API とブラウザの連携、コンテナ、ローカル版の Web）、`cellpose-gpu-image`、`windows-installed`（配布 ZIP の新規導入と更新）の 3 つの統合試験は、PR では実行しない。`main` への push、マージキュー、手動実行のときに、すべての領域とあわせて実行する。PR はマージキューを通して取り込むので、統合試験はマージの前に、先に並んだ PR と最新の `main` を組み合わせた状態で実行される。そのため、統合試験で失敗する変更は `main` に入る前に止まる。

Windows 版は、この 3 つを含む 7 つのジョブが、配布する `main` のコミットですべて成功している場合にだけ配布する。`main` で失敗した場合は、次の配布までに修正するか取り消す。

## 依存パッケージの記録とシークレット走査

シークレット走査は、固定版の gitleaks を検証してから、Git の全履歴と追跡中のファイルを調べる。そのため CI は `fetch-depth: 0` で checkout し、保存するのは件数と規則 ID だけ。

依存パッケージの記録は、Python パッケージのライセンスの根拠や、Web の直接依存のライセンス本文が欠けていると失敗する。この分類と表示の収集は根拠の確認であって、法的な適合性の判断ではない。範囲は [OSS の管理](oss.md) を参照する。依存の記録とシークレット走査の要約は 7 日で消える。生の検出結果、ログ、研究データを、成果物のアップロード対象に加えない。
