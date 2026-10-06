# Cytellect

蛍光顕微鏡画像の核検出・測定・統計・作図を行う Web アプリケーションのソースコードです。
開発中のプロトタイプで、Web、Windows ローカル版、Docker で配布しています。

- 公開サイト：https://cytellect.vercel.app/
- 最新の Windows 版：[0.1.0-local.15](https://github.com/genellect/cytellect/releases/tag/v0.1.0-local.15)
- 利用者向けの説明：[解析機能の説明](docs/implementation-overview.ja.md) · [公開画像ではじめる](docs/quickstart.ja.md)
- English: [README.en.md](README.en.md)

## リポジトリの構成

| ディレクトリ | 内容 |
|---|---|
| `apps/web` | Web 画面（Next.js） |
| `services/api` | API サーバー（FastAPI） |
| `services/worker` | 解析ジョブを実行するワーカー |
| `packages/analysis` | 測定・統計・作図の Python パッケージ（API とワーカーが共有） |
| `packages/contracts` | OpenAPI 定義と生成済みの TypeScript 型 |
| `services/proposal-worker` | 解析計画の提案を中継する Cloudflare Worker |
| `engines` | Fiji・モデル・Windows 実行環境の固定版とハッシュ |
| `infra`、`compose.yaml` | Docker 構成 |
| `fixtures/public` | 試験とデモに使う公開画像 |
| `tests`、`scripts` | 試験、セットアップ、配布物の作成 |
| `docs` | 設計・解析法・運用の文書 |

## 必要な環境

- Python 3.12、[uv](https://docs.astral.sh/uv/) 0.12.2
- Node.js 24、pnpm 11.19.0
- 核の自動検出に Fiji（`scripts/fiji_setup.py` が固定版を導入）

## ローカルで起動する

```sh
uv sync --locked --dev
pnpm install --frozen-lockfile

export CYTELLECT_DATA_DIR=/absolute/private/cytellect   # リポジトリの外のディレクトリ
export CYTELLECT_APP_ORIGIN=http://localhost:3000
export CYTELLECT_SECURE_COOKIES=false
uv run python scripts/fiji_setup.py /absolute/private/fiji --platform linux-x64
export CYTELLECT_FIJI_EXECUTABLE=/absolute/private/fiji
```

API、ワーカー、Web をそれぞれ別のターミナルで起動します。

```sh
uv run cytellect serve
uv run cytellect-worker
pnpm dev
```

`uv run cytellect invite --hours 24` で招待トークンを発行し、http://localhost:3000 で使います。Windows では `--platform windows-x64` を指定してください。

Docker の場合は、`CYTELLECT_RUNTIME_DIR` に UID 10001 が所有する非公開ディレクトリを指定して `docker compose up --build -d` を実行します。詳細は [docker-desktop.md](docs/docker-desktop.md) にあります。

## テスト

```sh
uv run ruff check .
uv run pytest
pnpm check
pnpm test
```

Fiji を使う試験は `uv run pytest -m fiji`、ブラウザ試験は `pnpm --filter @cytellect/web test:e2e` で実行します。Pull Request には CI の5つの必須チェック（`python`、`web`、`fiji-browser`、`local-windows`、`python-windows-314`）の通過が必要です。

## 配布

| 配布先 | 方法 |
|---|---|
| Web | `main` への統合で Vercel が自動デプロイ（[deployment.md](docs/deployment.md)） |
| Windows 版 | `local-release.yml` で ZIP を作成し、インストール後の受入試験を通った版を GitHub Releases に公開（[local.md](docs/local.md)） |
| 解析計画の提案 | Cloudflare Workers と D1（[proposal-deployment.md](docs/proposal-deployment.md)） |

## ドキュメント

- 設計：[architecture.md](docs/architecture.md) · [requirements.md](docs/requirements.md) · [roadmap.md](docs/roadmap.md)
- 解析法：[methods.md](docs/methods.md) · [common-statistics.md](docs/common-statistics.md) · [figures.md](docs/figures.md) · [validation.md](docs/validation.md)
- 運用：[security.md](docs/security.md) · [local.md](docs/local.md) · [fiji.md](docs/fiji.md) · [oss.md](docs/oss.md)

## 貢献とセキュリティ

開発の進め方は [CONTRIBUTING.md](CONTRIBUTING.md)、作業上の規則は [AGENTS.md](AGENTS.md) にあります。研究用の非公開画像や解析結果は、Issue・Pull Request・ログに含めないでください。脆弱性は [SECURITY.md](SECURITY.md) の窓口に報告してください。

## ライセンス

Apache License 2.0（[LICENSE](LICENSE)）。Fiji、モデルの重み、公開データセットは、それぞれのライセンスに従います。
