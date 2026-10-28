# CI の構成

PR、マージ前の一括検証、`main` で実行される CI のジョブと、その選ばれ方をまとめる。手元では `python3 scripts/dev.py check` で、PR の `python` ジョブと `web` ジョブと同じ検査を実行できる（[CONTRIBUTING](../CONTRIBUTING.md)）。

## ジョブ

CI は `.github/workflows/ci.yml` の 9 つのジョブからなる。PR では、変更したファイルが影響するジョブだけを実行する。`main` への push と手動実行（マージ前の一括検証を含む）では、統合試験を含むすべてのジョブを実行する。所要時間は 2026-10-28 の `main`（9bef468f）での実測。

| ジョブ | 内容 | PR | 一括検証・`main` | 所要時間 |
|---|---|---|---|---|
| `changes` | 変更したファイルから、実行する領域を選ぶ | 実行 | 実行（すべての領域） | 1 分未満 |
| `python` | Ruff、mypy、Linux でのテスト一式、解析計画と解析提案の検査、公開デモの実行環境と解析ソースの一致、公開ツリーと文書のリンクの検査、シークレット走査、依存パッケージの監査と SBOM | 常に実行（テスト一式などは `python` 領域のとき） | 実行 | 約 12 分 |
| `web` | API 契約の再生成、Next.js の検査・単体試験・ビルド、解析提案の Worker、公開サイトのブラウザ試験、ローカル版の Web 出力が配布物の境界に収まること、依存の記録 | `web` 領域 | 実行 | 約 5 分 |
| `lp` | Next.js の検査とビルド、LP のブラウザ試験 | `lp` 領域（`web` を実行しないとき） | 実行しない（`web` が同じ試験を含む） | — |
| `local-windows` | Windows のセットアップとランチャーの境界 | `windows` 領域 | 実行 | 約 4 分 |
| `python-windows-314` | Windows・Python 3.14 でのテスト一式 | `windows` 領域 | 実行 | 約 34 分 |
| `fiji-browser` | 実際の Fiji、API とブラウザの連携、本番のコンテナ、ローカル版の Web の配信 | 実行しない | `fiji` 領域 | 約 29 分 |
| `cellpose-gpu-image` | GPU 推論のイメージを CPU で動かし、CPU 版と同じラベルを返すこと | 実行しない | `fiji` 領域 | 約 6 分 |
| `windows-installed` | 配布 ZIP の新規導入と、前の版からの更新 | 実行しない | `windows` 領域 | 約 13 分 |

ジョブは並行して走るため、CI 1 回の待ちは最も長い `python-windows-314`（約 34 分）で決まる。実行しなかったジョブは、ブランチ保護には成功として報告される。

## 変更したファイルと領域

どのファイルがどの領域に当たるかは、`scripts/ci_changes.py` が決める（規則の試験は `tests/test_ci_changes.py`）。

| 領域 | 選ばれる変更 |
|---|---|
| `python` | 解析、API、ワーカー、`scripts`、`tests`、`engines`、`infra`、公開デモの実行環境（`apps/web/public/showcase/**`） |
| `web` | `apps/web`、契約、解析提案の Worker、解析・API・ワーカー、ローカル版のパッケージ化のスクリプト |
| `lp` | LP の部品・素材・試験 |
| `fiji` | `apps/web`、契約、解析・API・ワーカー、`scripts`、`tests`、Fiji、`infra` |
| `windows` | 解析・API・ワーカー、`scripts`、`tests`、`engines`、ローカル版の書き出し |

- **LP だけの変更**：LP の部品（`PublicLanding`、`Landing*`、`HeroFilm`、`optical-landing.module.css`）、`lp-metrics`、LP のブラウザ試験（`marketing`、`lp-*`）は `lp` だけを選ぶ。LP の素材（`apps/web/public/marketing/**`）と `fixtures/public/allowlist.json` は Windows 版の配布物にも含まれるため、`python` と `lp` を選ぶ。`lp` は API 契約の再生成、解析提案の Worker、デモのブラウザ試験、依存の記録を省き、pnpm のストアと試験用のブラウザをキャッシュから復元する。ヒーロー映像の制作用スクリプト（`scripts/lp_film/**`）は、どの領域も選ばない。
- **文書だけの変更**：`docs/**`、ルートの Markdown、`.github/` 配下の Markdown（PR・Issue のテンプレート）、`LICENSE`、`NOTICE` は、どの領域も選ばない。`fixtures/public/allowlist.json` の変更が `docs/` の画像の登録だけの場合も、文書の変更として扱う。Python のテスト一式が選ばれないときは、配布物に含める文書の試験を実行する。
- **すべての領域を選ぶ変更**：workflow、lockfile、パッケージの定義、`fixtures/` のその他のファイル、規則にないパス。トップレベルのディレクトリを追加するときは、`scripts/ci_changes.py` の規則とその試験も更新する。

公開ツリーの検査、文書のリンク検査、全履歴のシークレット走査は、どの変更でも実行する。

## マージまでの流れ

1. **PR の CI**：変更に関係するジョブを実行する。統合試験は PR では実行しないため、統合試験で見つかっていた境界のうち、数分で確かめられるものは PR のジョブに置く。
   - `web`：ローカル版の静的出力（`pnpm --filter @cytellect/web build:local`）を作り、`scripts/check_local_web_bundle.py` で配布物の許可リストに収まることを確かめる。生成するファイルが増えたとき（例：`sitemap.xml`）や、パッケージ化の許可リストを変えたときに、統合試験より先に失敗する。
   - `python`：`scripts/build_showcase_runtime.py --check` で、公開デモがブラウザで動かす Cytellect のホイールが、解析・API・ワーカーのソースと一致することを確かめる。Python を変えたら、同じ PR で作り直す（[公開デモ](showcase.md)）。
2. **一括検証とマージ**：マージはオーナーがルールのバイパス（`--admin`）で行う。バイパスは必須 CI も飛ばすため、マージする PR を最新の `main` にまとめたブランチで、統合試験を含む CI を 1 回実行してからマージする（手順は[チーム開発ルール](team-development.md)の「開発の流れ」の手順 6）。PR の本数によらず、待ちは CI 1 回分（約 35 分）で済む。
3. **`main` の CI**：マージ後の `main` で、すべてのジョブをもう一度実行する（次の節）。

`python-windows-314` は、所要時間を減らす準備として、遅いテスト 40 件の時間を記録する（`--durations=40`）。試験は減らさない。

## main で実行される統合試験と配布の条件

`fiji-browser`、`cellpose-gpu-image`、`windows-installed` の 3 つの統合試験は、`main` への push と手動実行のときに、すべての領域とあわせて実行する。1 本の PR を一括検証なしでマージした場合は、統合試験で失敗する変更が `main` に入った後に見つかる。その場合は、次の PR より先に修正を入れる。

Windows 版は、`python`、`web`、`fiji-browser`、`cellpose-gpu-image`、`local-windows`、`windows-installed`、`python-windows-314` の 7 つのジョブが、配布する `main` のコミットですべて成功している場合にだけ配布する（`.github/workflows/local-release.yml` が確かめる）。`main` で失敗した場合は、次の配布までに修正するか取り消す。

## 依存パッケージの記録とシークレット走査

シークレット走査は、固定版の gitleaks を検証してから、Git の全履歴と追跡中のファイルを調べる。そのため CI は `fetch-depth: 0` で checkout し、保存するのは件数と規則 ID だけ。

依存パッケージの記録は、Python パッケージのライセンスの根拠や、Web の直接依存のライセンス本文が欠けていると失敗する。この分類と表示の収集は根拠の確認であって、法的な適合性の判断ではない。範囲は [OSS の管理](oss.md) を参照する。依存の記録とシークレット走査の要約は 7 日で消える。生の検出結果、ログ、研究データを、成果物のアップロード対象に加えない。

## 実装の注意

図の描画に使う日本語フォント（`fonts-noto-cjk`、約 61 MB）は、Linux のジョブで `scripts/install_figure_font.sh` が導入する。遅いミラーが取得に 20 分以上かかり、`python` ジョブが試験の途中で 30 分の上限に達したことがあるため、取得が 20 秒続けて遅いミラーは打ち切り、別の公式ミラーで続きから取得する。導入するのは、apt の署名済みの索引にある SHA-256 と一致したファイルだけで、どのミラーからでも同じパッケージになる。照合したファイルは `dpkg` で直接導入する。`apt-get` に渡すと、同じ版を遅いミラーから取り直すことがあるため。
