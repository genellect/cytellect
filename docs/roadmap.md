# ロードマップ

MVP（画像の登録から検出・修正・測定・統計・作図までの一連の機能、Windows 版、公開デモ）は完了しました。この文書は、これからの開発計画と、まだ満たしていない受入条件を管理します。MVP 期の実装記録とマイルストーン（M0–M5）は [MVP 期のロードマップ](archive/roadmap-mvp.md)に残しています。

## 現在の提供状況

| 対象 | 状況 |
|---|---|
| 公開サイト | [cytellect.vercel.app](https://cytellect.vercel.app/)。LP、`/demo`、`/plan` で構成する。`/demo` は本番と同じ解析ワークスペースを、登録済みの公開画像でサーバーレスに動かす（[公開デモ](showcase.md)）。画像の追加は Windows 版・Docker 版だけで行い、公開サイトは研究画像を受け付けない。公開サイトの `/workspace` は `/demo` へ転送する。`main` へのマージで自動デプロイ |
| Windows 版 | [0.1.0-local.19](local-release-0.1.0-local.19.md)。作業データは既定で削除操作まで保持。Cellpose はクラウド GPU で実行できる（クラウド GPU は未作成のため、現時点では使えない） |
| Docker 版 | [Docker Desktop での利用](docker-desktop.md) |
| 解析提案（LLM） | 既定で無効。利用者が有効にした場合に限り動作し、月額の利用上限を設定した Worker で提供 |
| 核小体検出 | NCL の protocol 4.3.0（追加学習した Cellpose-SAM と境界補正）。[計算仕様](methods.md) |

## 今後の計画

### 研究室向け固定Docker版

固定版用の明示ランチャーを追加し、通常開発の起動と分離する。別経路では、外部の
配布記録で固定した manifest と実ローカル image ID を照合し、ビルド・pull・自動更新を
行わず、インストール単位の研究ボリュームを維持する。詳細は
[固定版の起動契約](docker-desktop.md#固定版を使う研究室向け起動経路配布受入前)。

手動保持（PR63）を含む統合ソース、B0既定と明示選択候補のモデル取得・来歴、
対応する実イメージと配布 manifest は別途レビューして確定する。このソース単位は
PR61/62/63を採用・mergeせず、実配布物や科学的な改善を成立させない。
ラボのOS/メモリ/空き容量を確認し、実環境での起動と保存・編集・測定を受け入れる。
全writer停止下のDB・artifact一体バックアップと互換版への復元は次の単位とし、
その完了までは異なるreleaseへの通常起動を拒否する。

### 1. 自研究室での実証

研究室の実画像で、検出精度・操作性・解析時間を評価し、核小体・細胞質のモデルを改良します。

- **独立したテストデータを最初に構築する。** 学習・条件調整に使わない実験回の画像を、評価専用として分けておきます。これがないと、精度の比較も実証も成り立ちません。
- 正解には研究者が描いた輪郭を使い、2 名が独立に描いて正解自体の一致度も測ります。
- 指標は、再現率・適合率・F1（IoU ≥ 0.5）、融合・過分割の数、面積・輝度の誤差とし、実験回ごとに集計して信頼区間を付けます。

### 2. 北里大学の他研究室での実証

研究対象や撮影条件の異なる画像で検証します。あわせて、解析基盤を AWS などのクラウドへ移します。移行先の選定と費用はオーナーが判断します（[比較資料](hosting-costs.ja.md)）。

### 3. 他の研究機関への公開

解析コードは誰でも使える形で公開を続けます。クラウド実行・共同利用・運用支援を、有料提供の候補とします。

### 評価する項目

モデルの検出精度、面積・輝度の測定誤差、手補正にかかる時間。

## 未完了の受入条件

| 項目 | 内容 |
|---|---|
| 非公開データでの検証 | 研究室の実画像による、検出と測定の生物学的な妥当性の確認 |
| 研究者による評価 | 複数の研究室の研究者による、作業の完了・時間・修正の負担・理解・再利用の評価（[評価タスク](usability-tasks.ja.md)） |
| Windows 版 | Cellpose は CPU では 1 視野に数十分かかり実用にならないため、推論をクラウド GPU（[設定](cloud-gpu.ja.md)）で行う。実 GPU での所要時間・費用と CPU との一致度の受入、Windows のセットアップ画面からの設定。別の PC で起きた Smart App Control によるブロックへの対応 |
| ホスト型の解析 | 公開 TLS とドメイン、利用者が不在の間の継続的な削除、運用サーバーの分離。研究画像をクラウドで受け付ける前に満たす |
| LP | 2026-10-23 にヒーロー映像（培養プレートから始まる実写の版）と本文（具体的な主張と解析例の実画面、「できること」4 つのタブ）をオーナーが承認した。残りは、ヒーロー映像の改良（Codex が担当、[美術方針](lp-art-direction.md) §9・§10）、研究室での撮影の可否、核小体の検出の前後比較の画像と研究室の利用者の声を公開してよいかの確認 |
| 今後の機能 | アカウント、チーム、長期保存、決済 |

検証の層と記録の方法は [validation.md](validation.md) に従います。CI の成功や公開した事実は、科学的な妥当性の証明にはなりません。


## Laboratory manual-retention implementation

A scoped source change adds explicit manual workspace retention with consistent
API/worker/UI behavior and a durable guard against returning the volume to TTL.
Default non-lab retention remains 24 hours. Metadata-only checks do not establish
installed browser behavior, image correctness or delivery readiness. Remaining:
independent source review, integrated PR/model selection, pinned Docker release,
quiesced DB/artifact backup/restore, hardware/resource confirmation, and fresh
real-input installation acceptance. No automatic merge/default-model switch or
production PoC is part of this change.
