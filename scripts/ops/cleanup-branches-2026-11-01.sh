#!/usr/bin/env bash
# =============================================================================
# Cytellect のリモートブランチ整理（2026-11-01 に照合した一覧で固定）
# =============================================================================
#
# 背景
#   genellect/cytellect は公開リポジトリで、2026 年 10 月の 1 か月でブランチが 181 本まで溜まった。
#   運用は squash merge で、リポジトリ設定 delete_branch_on_merge がオフだったため、
#   マージ済みのブランチも消されずに残っていた。
#   オーナー（genellect）は、有名な OSS に育てることを見据えて、次を決めた。
#     - マージ済み PR のブランチを削除する。
#     - マージせずに閉じた PR のブランチは不要。コミットは refs/pull/<番号>/head に残り、
#       PR の画面からブランチを復元できる。
#     - PR のないブランチも原則として不要。main にない作業が残る 5 本は、オーナーが判断するまで残す。
#     - 今後は、マージと同時にブランチを自動削除する。
#     - どのような場合もマージはしない。
#
# 目的
#   次の 2 つだけを行い、誰が何度実行しても同じ最終状態にする。
#     1. 下の TARGETS の 172 本を削除する（マージ済み 131、閉じた PR 33、PR なし 8）。
#     2. delete_branch_on_merge を true にする。
#   完了すると、リモートに残るのは KEEP の 10 本だけになる
#   （2026-11-01 より後に作られたブランチは削除せず、そのまま残る）。
#
# 越えてはならない一線（このスクリプトが守る）
#   - 何もマージしない。何も push しない。行うのはブランチの削除だけ。
#   - TARGETS にあり、かつ照合したときの SHA のままのブランチだけを消す。
#     172 本は 1 回の atomic push で消すので、1 本でも SHA が違えば GitHub は全体を拒否し、何も消えない。
#   - KEEP（main、オープン中の PR、判断待ちの 5 本、作業ブランチ）と、一覧にないブランチには触れない。
#   - タグ、Releases、ブランチ保護、ルールセットは変えない。変える設定は delete_branch_on_merge だけ。
#   - TARGETS を書き換えた版は、整合性の検査で止まる。一覧を変えたい場合は、オーナーが新しい一覧を作る。
#
# 使い方（このファイルを編集せずに実行する）
#   bash cleanup-branches.sh            # 確認だけ（読み取りのみ。何も変えない）
#   bash cleanup-branches.sh --apply    # 削除と設定の変更を実行する
#   必要なもの: bash、git、gh（gh auth login 済みで、genellect/cytellect の管理者権限）。
#   push にも、その gh のアカウントを使う。ルールセットで削除が禁じられたブランチがあれば、終了コード 4 で何も消えない。
#   どのディレクトリから実行してもよい。手元の checkout は使わず、変更もしない。
#
# 終了コード
#   0 完了（または確認で問題なし）  2 一覧と現状が違う（何も変えていない）
#   3 道具・権限・一覧の整合性の問題（何も変えていない）
#   4 削除が拒否された（atomic なので何も消えていない）  5 実行後の検証で食い違い  64 引数の誤り
# =============================================================================
set -euo pipefail
export LC_ALL=C

readonly REPO="genellect/cytellect"
readonly URL="https://github.com/${REPO}.git"
readonly TARGETS_HASH="30fd1682e643f103d4d03eddec61ba1834784a46"
readonly KEEP_HASH="b1950f3cc124d39efe747efd2c88f24c7524e2fc"

# 削除する 172 本: <照合した SHA> <ブランチ> <区分> <PR>
#   merged = 先頭がマージ済み PR の head と一致 / closed = マージせずに閉じた PR
#   no-pr-in-main = PR なし・内容は main に反映済み / no-pr-old = PR なし・2026-10-06〜07 に分かれた古い作業
targets() { cat <<'LIST'
a73631706b8670e69c72ac2e49ae2c43cb16d1b8 auto-background no-pr-old -
d096a24bc4551125f690f5e3b3e5dab0959dfd51 chore/ci-pr-boundaries merged #139
590575e0ea1029d55c9fa609b47bb6f7b68303c5 chore/ci-speed merged #80
3840c40287763f3e537c40e3d5423608f193f416 chore/ci-supply-chain closed #86
d8e24ebbda4b09303315d54423401b63e8acefd2 chore/codeql merged #164
558c2aa43025a0c7ff02ed840e01b09e17266753 chore/custom-domain merged #152
e9d5b37fb2a79e70a1d4d6fb6e513fe6760cdb00 chore/dev-entrypoint merged #94
8737a6eccc0b973ec952ed6567ad90c83af55850 chore/docs-ci-fast merged #115
58e5f26deb85676085d66586bdc3415407f2cb76 chore/gpl-corresponding-source merged #161
c53e87586997648b19ff761cc522df3b3cc29a8a chore/lp-ci-fast-path merged #92
31187ed077d6b384b7d42f465004c684f97c8320 chore/review-2026-10-27 no-pr-in-main -
ef8ac5001825290d733421447e659ce382665407 chore/scan-font-checksum merged #157
f4e62c93ccd93eac276f02075abe323471a2e85f chore/scan-font-checksum-2 closed #158
adc6ebf2b3afc7b2203b06c01c856acde7c2dc8c chore/site-download-local21 merged #176
f40b1da9291c968ad7b732ebd03bba38f68196f9 chore/vercel-preview-branches merged #171
93d97eecf6d834d177e95cf71a7dd2a3a330ec2e chore/windows-release-group-comparison merged #142
f74bc4f9c75238a5d1809f07cc364853d5c0314a chore/windows-shard-weights merged #141
707f007a5fc579dd84c264b97622ba4b9ddde5f0 ci/release-any-green-main merged #172
be38fef8f84dd3fe30120522966ca00eb674c15f claude/cool-feynman-spwegw merged #52
e9ffc0957b6e6101d5e44f4bddb3789de86f8c13 claude/cool-feynman-spwegw-ci merged #39
1884a81a13938dbadda4e84cac4e646301d1ec35 claude/cool-feynman-spwegw-llm merged #31
0e5c51cf696724305df1e8742a865a7911c5224b claude/cool-feynman-spwegw-overview merged #38
d74be3416c009573ad006fbfe95777f5fa9ec653 claude/cool-feynman-spwegw-release merged #34
049539114d4eca8c489c1450d51110f53a270a50 claude/cool-feynman-spwegw-ux merged #30
0c7f0cfa7ca43998548c1804d79e9bcaa5c5f56f claude/eloquent-darwin-e9l1hn merged #113
df98d7221d94a9fc7c22d3484a9e4670a1e70559 claude/exciting-ptolemy-7hnkao merged #163
61071f29a0a1781bdb8cac88aff7774c9c1e2ed0 claude/kind-knuth-8v1ao2 merged #179
d73a70b948dda7db446ec329fddd5599dbb23179 claude/magical-einstein-yqpl7v no-pr-in-main -
ed15415ac5f0e46c64ac2319ca4ca40eb864b1ed claude/optimistic-davinci-oz7zzc merged #96
8ea3825c91718de2853a54054bd8c6dc62142a86 claude/tender-ritchie-0a078r no-pr-in-main -
0a7a19f9d1f4ce1213501be29fab51744d29f01c claude/trusting-newton-utxdb1 merged #150
5300988d92fad21cdca44010e1eec384ed29239c claude/wonderful-bell-9aonvf merged #81
32414f215c9037e71a3d0d70a306d048f0839d72 claude/wonderful-ptolemy-pyybzn merged #134
854b5423528002d87fb60d3b84a33dd32fe30eb2 codex/accepted-workspace-release merged #49
4cddca0ae00521a96d8f7f513f418d460616d1c0 codex/activate-workspace-e2e merged #37
5de96f616f42235d5c150229286e4be68d81e039 codex/batch-workspace-repair closed #42
39007848ba42588d17d75cb52b86d9b76ec3f1ac codex/claude-cloud-setup merged #33
f4e06535a21d80d03a65cec2d1e23f982656d93e codex/demo-performance-n03 closed #108
d0c19fbf520c5f2669133871390e7ba90adecc20 codex/descriptive-field-summary merged #107
1576f06cd94bc75bf784283164faa6d6c2791226 codex/docker-owner-session merged #41
d654088213256baa045226fc1ef508ebdfd187f5 codex/group-comparison-alignment-review closed #105
d43d31dc95dbd040b9f73e083f11e6478450556c codex/group-comparison-crosscheck closed #101
2af646a6f16e1eff6767d28cc2b9785559a99ed6 codex/group-comparison-public-data closed #99
05a7fbab3e1f4c883b9c65ee9c4cb8d6489eac0f codex/group-comparison-resource-benchmark closed #100
9db5d140f74e7f9fa63ba2f3848a9a9c965991c0 codex/group-comparison-ux-review closed #106
5da58524cdf101df3dea7d32799741ea8bbb83ac codex/installed-comparison-acceptance merged #48
f45d07573187f95ee08e4778f9c04d4f3e3eb904 codex/japanese-readme-editorial merged #55
d64aa9c2cda569f9345f2e650d02db2a89b9207a codex/jump-cellprofiler-reference closed #102
7aa3cb7201cf651447a5457cf7a9b26032becf91 codex/ncl-cellpose-checkpoint-20261008 merged #50
3c2dafd69ca0dee4ad59f439c32436b4aa9453db codex/ncl43-release18-delivery closed #54
c03215c5e4f20f11e64b27e7b8ebd8dde65995cb codex/optical-landing-preview merged #59
7f65970cfb38b962f6b962355e3e30cfc9b80298 codex/production-delivery merged #35
952fbdc390bbeda83fd693c5931fb0babc058796 codex/public-image-integration-test closed #103
7877410d9a667c1233b7fcda39b8cbfe4ca2e153 codex/publish-local16-receipts merged #40
7b9ca76b49553c67dd1637626fe8771a35380bc8 codex/readme-japanese-statistics-link merged #57
e704cb2ca755a902a8647218ead146f1601354ac codex/showcase-ds6a-nucleolar-scene closed #104
bc7520a002677b9914e40b6f341ff1e97515048b codex/sol-workspace-integration merged #32
a99b4980b868fe35bc4f2da0118af2294148e589 codex/unresolved-nucleoli-design closed #109
bd7251a0b40b1f5b79574ddade61e461c172a441 codex/windows-local15-publication merged #36
7f55575e8ed6f3d8c4be8da7b460dd82b837f44f codex/windows-msix closed #88
7180a62b413ca7a3c722b3a93404ffda75341c4a codex/windows-upload-ready merged #53
828ec01dde6650b11e1065f1eb1384a4dae7c80d codex/workspace-integration-repair merged #46
309a0c3e3fdb0fd0f11d7fb857e8344387cc4ed2 codex/workspace-release-record merged #47
3fc6f8bf846029af23c419fc29e191c32acc48af docs/agent-report-language closed #87
36abeda0482a1d0b7cf608f1a0cce7a64afcf9bb docs/analysis-overview-refresh merged #121
a7c30e4a9d17cbbc6624a4266027decf97fe9df9 docs/architecture-image merged #165
db26105563003f97a089d0c18d821e27c7f876a6 docs/bilingual-team-workflow merged #60
929b1f86b11810d83b10f5603481df79f16f87bc docs/ci-plain merged #118
fefeb38ad3a1a8f71c172c0c720a5a4d1f9870e9 docs/cloud-development-plan merged #129
152ed1cd6fc2d88b0125b09ce286dc7d0793d7ce docs/development-environment-guide merged #133
d39c7ec0ec709cf213e1c01b8b5275fd2080a0f8 docs/docker-desktop-guide merged #135
dba57e0738c22819d86bd9b9010ce7e4354f64a0 docs/docs-navigation merged #97
4faec0494e37cbc242291db6da83c73655037eae docs/frontend-skill merged #149
3226dff5da64fe3aa3524a6c0439f18699ed7aec docs/ga4-hostname merged #153
5a6c4bf191f42b7be86ddcd5adbf0eb83cea9b97 docs/index-security closed #85
36d2908d52f9e549334c4274621864b95d9ffc8f docs/local11-release-20261004 merged #14
e62b6adb5999ff22aaa894cba91f87ae0306a5a6 docs/lp-art-direction-ref merged #123
c0b8c0d4f5d0b59cc9201190ac01e0f252211bc0 docs/merge-queue merged #137
fb240922d39c104f9a90d3224dae2e6fedd8e8cf docs/model-delivery-roadmap closed #67
35f88cb92ddb42c844071c54b6981f17b96d11a5 docs/oss-ja merged #148
854eac7265e7dc5c6e2146a41b18e5907204ff0e docs/owner-approval-rules merged #147
482098baf26d3e68e2dda9e8763d4ac70c8c7754 docs/plain-style merged #117
928b92685f296fb66809abee55205a1e1d19ee83 docs/pr-template-background merged #119
13e544f9eedf6015ebdeb43ce68ed61fd2b455d0 docs/product-mission merged #98
f3114a1f8a6b79452e187134ed82b42851177d93 docs/readme-accuracy closed #95
9ece77c92a2cdfaac51ddbfd2d151be320b4ea13 docs/readme-architecture merged #114
e9e8d46c1ec584daa9951c17531dbb29479214ae docs/readme-intro merged #116
5ee831d629b58596ff3de25d8a73d107a3f0b6e0 docs/readme-licenses merged #146
0586b88c16ceb2d15470032f527201d65f33e40d docs/readme-security merged #170
92326f05087e4bb24b5e7e56980882242ad52711 docs/release-0.1.0-local.19 merged #78
35c6fb998e25e846fa1f3f53e53309e292cf5896 docs/review-focus merged #136
7e96f1c4655da5cadbed67b557a42e69d3a357ec docs/segmentation-model-roadmap merged #145
39a8411646623ef547d217b2a43b4d463a9516b1 docs/windows-local-20 merged #144
5ef6d41092746ac4f519bfa580fa089cdaf3b393 feat/area-only-20261004 merged #18
e4c011d52d53bada007d10251adb8591fdd3fcdd feat/cellpose-cloud-gpu merged #71
40e8df6f810026faf778bc023afd0de4ca51d4a9 feat/cellpose-modal merged #82
ae60f1550a44b4d2389d09087375477ca03cc6e9 feat/cloud-account-local merged #156
02b417203b6c6783f0a12a15b4a446822cd0ff5a feat/cloud-auth-worker merged #154
06ea400f06fbcc0cf3ebf502344e8a53f8404628 feat/common-statistics-integration merged #26
ec7f922bf51d106477d15c5de5bbf9f348abeb35 feat/comparison-provenance-20261004 merged #16
23975ae44e426ca4bb978db30e00f043ffa7fd6f feat/docker-human-e2e closed #28
7eb19814343c1a512029b31b1d7b18bccf3a5869 feat/embed-update-public-key merged #162
b8fb46ec582cc113a1f2ce97c0ddcd1e86766966 feat/field-qc-overview-20261004 merged #21
b075eb9b285acf8d8b4b1a4c4891338e7969e5e9 feat/guided-regions-20261003 merged #11
54700d594080f8c9e71c350a03ed0f4a046b0ad0 feat/immersive-product-lp-20261004 merged #22
b25a8ee72bda5ce4314b95d7dedc7743a0bd6a17 feat/lab-fixed-image-build closed #66
139498cc897ba2a8712bafe85d8254ab8c7e9cb0 feat/lab-manual-retention closed #63
6d526d119e922cfa99f2d78e299abf70f5bf40c3 feat/lab-release-start closed #64
127f3f9eb316bcdd0519b88838065bea44e48e4f feat/lp-conversion-paths merged #177
3a4b4619f21f4c733f12cacd6bbd777d4fceaba2 feat/lp-film-blender closed #76
aeff10fae5768e9f438fdbf5bbdae291acbfd67a feat/lp-ga4 merged #27
a21006e7f99864e32391a001bf78e7ced1a2edfc feat/lp-patient-impact closed #138
6044474afeed4197be8aed17c51f31d8fa6a4ef0 feat/lp-patient-impact-line merged #140
85554d957e8f4be25ec1d84d0173969087571134 feat/lp-release merged #79
5fc2716f0d4cb2c1d5170df71ec934b1fe8a2139 feat/methods-and-recipe-guidance-20261004 merged #20
491c7e4f97d80879dbef47c135d2025502701812 feat/ncl-envelope-experimental closed #65
2d080c59c1c3c73234c37f8ce3bb579b641e12fd feat/ncl-pending-candidates closed #62
e5202a96d50581d00e513336d4c1c1b34fafd430 feat/ncl-poc-model closed #61
136eab8ff41af0fd0ee5d0b0936525013f6c5569 feat/nuclear-region-comparisons-20261004 merged #12
53a067c855dcb4d0013cf99bf38fdfbc101044f4 feat/paid-access-codes closed #89
f07487c12351198574ce442b400b05ca359dae51 feat/plan-and-batch-workflow-20261004 merged #13
e511802262899ff28fa3a4b3e0ff8665823fdc0f feat/public-upload-allowlist merged #125
bac508c3046449777c1b402085849a8ad24d9d6c feat/research-workflow-20261003 merged #10
916c2279a9abf7f777fba31085c964d940181ba5 feat/researcher-traceability-20261004 merged #15
0525203d23e14dc887c9cae9386f96f48f9d82ff feat/signed-windows-runtime-20261004 merged #17
2b3812a17474a672727452dd20191a19bc045a6b feat/site-download-installer merged #168
e399908c09507a4765391fdacf48cb6c737be65e feat/traceable-display-and-figures-20261004 merged #19
99aa28d6267c2442694eb756150cbf6a1c59f4a5 feat/unresolved-nucleoli-missing merged #111
b64594b7bf3556a26492f169de48d997b33b42a3 feat/windows-installer merged #155
54ebb040a678a5bbb79390ca5921d9993cc31b8a feat/windows-manual-retention merged #69
81047dc8001d4ecb456eab1aceafec278d9533e8 feature/local-browser-runtime merged #2
e47970cb3873c23da25a94f952d2337d91c38a6f feature/local-mvp-continuation merged #1
83581d29a77e3a5fad820aab53b72de8b1501b8b feature/published-windows-release merged #3
9fb2366e229cdff816edd7b757aa63cdf2de0c35 fix/admin-only-on-api-host merged #160
1a123be2fadd996f84ea14bb85ec7bef0fd11797 fix/beginner-install-wording merged #169
0d1fb1614c06ab691146347652f6a0b2767dac92 fix/cellpose-modal-measure closed #83
690887823a2ec91b6b4db339513bc10b956f0c1b fix/ci-figure-font merged #132
248623bff8055e93351c770ff1f35678075d90f2 fix/ci-shard-artifact-rerun merged #159
586e02e3f02480bd1d271187d2fecde3b1d362d8 fix/completion-audit merged #6
c3a6970ffc85d15c4cacaf1aa1fe5750d601deda fix/dev-origin closed #84
a2c6f75b73ea48f42e43c28af95817dc4a3feaa6 fix/filelock-audit merged #93
084b02e3360748fe5c3850c3ced7b18cbc4d8ea5 fix/font-subset-lp merged #178
20bbcf8b3cab2a7ef2845f366f14a7bd0d4c4d6e fix/image-transmission-text merged #166
5becbe2c8ac6dc92907c4e7640e170d57e49ca6d fix/installed-acceptance-retention merged #77
a8d67becac2a8d731a4c529c365c179487eca390 fix/jump-c1-console-401 merged #167
06757ab4264ab6248bc21cd13b4f73215ff0fcad fix/local-static-flight merged #24
142b954a01fafbc449a6c73f96c3384592e6bfc6 fix/lp-footer-genellect-copyright merged #75
006f8b430bbbda348d7bbca1b01903c66f019b76 fix/lp-mobile-composition-20261004 merged #25
39c189b138bd6d1957114b01fe906a1a23dd571d fix/methods-channel-role merged #8
96812c46a33c54ce4d801ee76475afba6927ce8f fix/methods-manual-edits merged #130
493970e6253159f47db3c2839344f81c40a2559a fix/modal-gpu-availability merged #143
30e9d61bc45260be8909f05c2251a614aef12cde fix/modal-inflight-drain merged #126
50281945c43142bec4a53c90bb51f7218dbbd670 fix/next-security merged #73
f1332261d946328aa7702c528557754cbc4dd34c fix/ome-xml-comment merged #131
4743c9ec34a5804d74cf3543369f6302b0e67819 fix/pillow-certifi-security merged #70
5eeef2e4006203f6d0e75e1af5c8373d860de8d7 fix/proposal-without-metrics merged #124
24a80a19b4234183942c505cb46e93c3ed6b3015 fix/region-intake-errors closed #128
76ddc9bcfab9f9c7a38e7ac1cb51f03e4637a2c8 fix/registered-caption-bundle merged #23
7b74f6e23e57fd6f9da0663e377e43788ba19b7d fix/release-notes-ja merged #175
dd9c863aa10594f3aefd8b7d64fb7edf68567c3b fix/statistics-workflow-audit merged #4
c64eb613102765766fbd87b960c0b27a633e3b07 fix/windows-cellpose-setup closed #68
044b666869530bdbe631ccbec6f925497c60f592 fix/windows-setup-cloud-cellpose merged #72
26b1fd68d5d7522e8a600b1b549aa74aa19a524e fix/workspace-review-ui merged #127
aa4ee31ecc1ef88a83300c95570a5ac1f78a2661 genellect-patch-1 merged #56
01d59c122bce932fa24477e9f29975c8a6191872 genellect-patch-2 merged #58
e024c8f4e22e25cfa4d750edfaf2b7d9b4517e3d genellect-patch-3 no-pr-in-main -
813183c69a3a5b4c93b24d51e636243ec27082bf gfp-gated-comparison no-pr-old -
8a006294982239a7798eeb34f77e20e54992bdc5 ncl-ratio-comparison no-pr-old -
e902b49944ea8d1acb96c9c816dbd515f337e50d release/local-preview-10 merged #9
ff09d02d5429baeaba197295f91a003b897ab7ec release/local8-acceptance merged #5
0d7b8731e9d5d85f504964c657ca81e40db71825 release/local9-acceptance merged #7
563e13ea662af38660c905a9e2187cabce9ad0f3 workspace-general-method-card no-pr-old -
LIST
}

# 残す 10 本（このスクリプトは触れない）
keep() { cat <<'LIST'
chore/merge-batch-20261028
chore/merge-batch-20261028b
chore/merge-batch-20261028c
chore/merge-batch-20261028d
ci/smart-app-control-audit
claude/funny-clarke-f9hffd
docs/windows-one-click-access
feat/windows-msix
main
review/ncl-envelope-dependencies
LIST
}

mode=check
case "${1:-}" in
  "") ;;
  --apply) mode=apply ;;
  *) echo "使い方: bash cleanup-branches.sh [--apply]" >&2; exit 64 ;;
esac
[ $# -le 1 ] || { echo "使い方: bash cleanup-branches.sh [--apply]" >&2; exit 64; }

say() { printf '%s\n' "$*"; }
fail() { code=$1; shift; printf 'エラー: %s\n' "$*" >&2; exit "$code"; }
work=$(mktemp -d); trap 'rm -rf "$work"' EXIT

say "== Cytellect ブランチ整理（一覧は 2026-11-01 時点） 実行の種類: $mode"

# 1. 道具・一覧の整合性・権限
command -v git >/dev/null || fail 3 "git が見つからない"
command -v gh >/dev/null || fail 3 "gh が見つからない"
[ "$(targets | git hash-object --stdin)" = "$TARGETS_HASH" ] || fail 3 "TARGETS が書き換えられている"
[ "$(keep | git hash-object --stdin)" = "$KEEP_HASH" ] || fail 3 "KEEP が書き換えられている"
[ "$(targets | wc -l | tr -d ' ')" = 172 ] || fail 3 "TARGETS が 172 本ではない"
targets | awk '{print $2}' | sort > "$work/target-names"
keep | sort > "$work/keep-names"
[ -z "$(comm -12 "$work/target-names" "$work/keep-names")" ] || fail 3 "TARGETS と KEEP が重なっている"
gh auth status >/dev/null 2>&1 || fail 3 "gh にログインしていない（gh auth login）"
admin=$(gh api "repos/$REPO" --jq '.permissions.admin' 2>/dev/null || true)
[ "$admin" = true ] || fail 3 "gh のアカウントに $REPO の管理者権限がない"
say "道具・一覧の整合性・管理者権限: OK"

# 2. 現在のリモートのブランチと照合する
git ls-remote --heads "$URL" | awk '{sub("^refs/heads/", "", $2); print $1, $2}' | sort -k2 > "$work/remote" \
  || fail 3 "リモートのブランチを読めない"
targets | awk '{print $1, $2}' | sort -k2 > "$work/targets"
# 状態: delete = 照合した SHA のまま / gone = すでにない / moved = SHA が違う
awk 'NR==FNR{now[$2]=$1; next}
     { if (!($2 in now)) print "gone", $1, $2
       else if (now[$2]==$1) print "delete", $1, $2
       else print "moved", $1, $2, now[$2] }' "$work/remote" "$work/targets" > "$work/plan"
n_delete=$(grep -c '^delete ' "$work/plan" || true)
n_gone=$(grep -c '^gone ' "$work/plan" || true)
n_moved=$(grep -c '^moved ' "$work/plan" || true)
say "削除の対象 172 本: 照合した SHA のまま $n_delete / すでに削除済み $n_gone / SHA が変わった $n_moved"
if [ "$n_moved" != 0 ]; then
  say "SHA が変わったブランチ（照合した SHA → 現在の SHA）:"
  grep '^moved ' "$work/plan" | awk '{print "  " $3 "  " $2 " → " $4}'
  fail 2 "一覧と現状が違うため、何も変えずに止める。オーナーに報告する"
fi
say "残すブランチ（KEEP）の現状:"
while read -r b; do
  sha=$(awk -v b="$b" '$2==b{print $1}' "$work/remote")
  say "  ${b}  ${sha:-（リモートにない）}"
done < "$work/keep-names"
awk '{print $2}' "$work/remote" | sort > "$work/remote-names"
extra=$(comm -23 "$work/remote-names" <(sort -u "$work/target-names" "$work/keep-names"))
if [ -n "$extra" ]; then say "一覧にないブランチ（2026-11-01 より後に現れた。触れない）:"; printf '  %s\n' $extra; fi
setting=$(gh api "repos/$REPO" --jq '.delete_branch_on_merge')
say "delete_branch_on_merge の現在の値: $setting"

if [ "$mode" = check ]; then
  say "確認だけを行った。何も変えていない。実行するには --apply を付ける。"
  exit 0
fi

# 3. 削除（atomic push。1 本でも条件が合わなければ全体が拒否される）
if [ "$n_delete" != 0 ]; then
  git init -q "$work/repo"
  set --
  leases=()
  while read -r _ sha b; do
    leases+=("--force-with-lease=refs/heads/$b:$sha"); set -- "$@" ":refs/heads/$b"
  done < <(grep '^delete ' "$work/plan")
  # push は、管理者権限を確かめた gh のアカウントで行う（手元の git の認証情報に左右されない）
  if ! git -C "$work/repo" -c credential.helper= -c "credential.helper=!gh auth git-credential" push --atomic --porcelain "${leases[@]}" "$URL" "$@" > "$work/push.log" 2>&1; then
    sed 's/^/  /' "$work/push.log" >&2
    fail 4 "削除が拒否された（atomic なので何も消えていない）。オーナーに報告する"
  fi
  say "削除: $n_delete 本を 1 回の atomic push で削除した"
else
  say "削除: 対象はすべて削除済み。push はしない"
fi

# 4. 自動削除の設定
if [ "$setting" != true ]; then
  [ "$(gh api -X PATCH "repos/$REPO" -F delete_branch_on_merge=true --jq '.delete_branch_on_merge')" = true ] \
    || fail 5 "delete_branch_on_merge を true にできなかった"
  say "delete_branch_on_merge: false → true"
else
  say "delete_branch_on_merge: すでに true"
fi

# 5. 検証
git ls-remote --heads "$URL" | awk '{sub("^refs/heads/", "", $2); print $2}' | sort > "$work/after"
left=$(comm -12 "$work/after" "$work/target-names")
[ -z "$left" ] || { printf '  %s\n' $left >&2; fail 5 "削除したはずのブランチが残っている"; }
missing_keep=$(comm -13 "$work/after" "$work/keep-names")
[ "$(gh api "repos/$REPO" --jq '.delete_branch_on_merge')" = true ] || fail 5 "delete_branch_on_merge が true ではない"
say "検証: 削除の対象 172 本はリモートに残っていない。delete_branch_on_merge は true"
say "残っているブランチ（$(wc -l < "$work/after" | tr -d ' ') 本）:"
sed 's/^/  /' "$work/after"
[ -z "$missing_keep" ] || { say "KEEP のうちリモートにないもの（このスクリプトは消していない）:"; printf '  %s\n' $missing_keep; }
say "完了"
