#!/usr/bin/env bash
# =============================================================================
# Cytellect のリモートブランチ整理 2（2026-11-01 に照合した 5 本で固定）
# =============================================================================
#
# 背景
#   2026-11-01 に、ブランチ 172 本を削除し、delete_branch_on_merge を true にした
#   （scripts/ops/cleanup-branches-2026-11-01.sh、コミット 6f7cb6a9）。そのときはオーナーの判断待ちとして、
#   PR のない 5 本を残した。オーナーは次のとおり判断した。
#     - review/ncl-envelope-dependencies：内容を閉じた PR #181 に残し、目的と組み込みの条件を Issue #182 に
#       記録した。ブランチは削除する。PR #181 の画面から復元できる。
#     - chore/merge-batch-20261028〜d の 4 本：採用しなかった「まとめて検証してからマージする」CI の案。削除する。
#     - どのような場合もマージはしない。
#
# 目的
#   下の TARGETS の 5 本だけを削除し、誰が何度実行しても同じ最終状態にする。
#   完了すると、残るのは KEEP の 5 本（main と、オープン中の PR #151・#173・#174・#180 のブランチ）と、
#   一覧の照合より後に作られたブランチだけになる。設定は変えない（delete_branch_on_merge は表示だけ）。
#
# 越えてはならない一線（このスクリプトが守る）
#   - 何もマージしない。何も push しない。行うのはブランチの削除だけ。
#   - TARGETS にあり、かつ照合したときの SHA のままのブランチだけを消す。
#     5 本は 1 回の atomic push で消すので、1 本でも SHA が違えば GitHub は全体を拒否し、何も消えない。
#   - KEEP と、一覧にないブランチには触れない。
#   - タグ、Releases、ブランチ保護、ルールセット、リポジトリの設定は変えない。
#   - TARGETS を書き換えた版は、整合性の検査で止まる。一覧を変えたい場合は、オーナーが新しい一覧を作る。
#
# 使い方（このファイルを編集せずに実行する）
#   bash cleanup-branches-2.sh            # 確認だけ（読み取りのみ。何も変えない）
#   bash cleanup-branches-2.sh --apply    # 削除を実行する
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
readonly TARGETS_HASH="86ab88d8e6aa25fcfcb5c7875c543c20913e7356"
readonly KEEP_HASH="5768da6fdeef9111427e9720af8e58ce108ad2c1"

# 削除する 5 本: <照合した SHA> <ブランチ> <区分> <PR>
#   closed = 内容を閉じた PR に残した / no-pr-unadopted = PR なし・採用しなかった CI の案
targets() { cat <<'LIST'
78297bd9ddb2e59561484c2043d876e920f3264b chore/merge-batch-20261028 no-pr-unadopted -
5a0b79aba6f891cdb70d4a68ac8dfb60d7c174bb chore/merge-batch-20261028b no-pr-unadopted -
48fd7d7a729b7856cd001d9b497270bb8b8c0eff chore/merge-batch-20261028c no-pr-unadopted -
d8ddceefecf8e5a0e5d1b72d6d4265659368c0db chore/merge-batch-20261028d no-pr-unadopted -
57c60f18a4b578115cf56f759add9c920372463f review/ncl-envelope-dependencies closed #181
LIST
}

# 残す 5 本（このスクリプトは触れない）
keep() { cat <<'LIST'
ci/smart-app-control-audit
claude/funny-clarke-f9hffd
docs/windows-one-click-access
feat/windows-msix
main
LIST
}

mode=check
case "${1:-}" in
  "") ;;
  --apply) mode=apply ;;
  *) echo "使い方: bash cleanup-branches-2.sh [--apply]" >&2; exit 64 ;;
esac
[ $# -le 1 ] || { echo "使い方: bash cleanup-branches-2.sh [--apply]" >&2; exit 64; }

say() { printf '%s\n' "$*"; }
fail() { code=$1; shift; printf 'エラー: %s\n' "$*" >&2; exit "$code"; }
work=$(mktemp -d); trap 'rm -rf "$work"' EXIT

say "== Cytellect ブランチ整理 2（一覧は 2026-11-01 時点） 実行の種類: $mode"

# 1. 道具・一覧の整合性・権限
command -v git >/dev/null || fail 3 "git が見つからない"
command -v gh >/dev/null || fail 3 "gh が見つからない"
[ "$(targets | git hash-object --stdin)" = "$TARGETS_HASH" ] || fail 3 "TARGETS が書き換えられている"
[ "$(keep | git hash-object --stdin)" = "$KEEP_HASH" ] || fail 3 "KEEP が書き換えられている"
[ "$(targets | wc -l | tr -d ' ')" = 5 ] || fail 3 "TARGETS が 5 本ではない"
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
say "削除の対象 5 本: 照合した SHA のまま $n_delete / すでに削除済み $n_gone / SHA が変わった $n_moved"
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
if [ -n "$extra" ]; then say "一覧にないブランチ（一覧の照合より後に現れた。触れない）:"; printf '  %s\n' $extra; fi
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

# 4. 検証
git ls-remote --heads "$URL" | awk '{sub("^refs/heads/", "", $2); print $2}' | sort > "$work/after"
left=$(comm -12 "$work/after" "$work/target-names")
[ -z "$left" ] || { printf '  %s\n' $left >&2; fail 5 "削除したはずのブランチが残っている"; }
missing_keep=$(comm -13 "$work/after" "$work/keep-names")
say "検証: 削除の対象 5 本はリモートに残っていない"
say "残っているブランチ（$(wc -l < "$work/after" | tr -d ' ') 本）:"
sed 's/^/  /' "$work/after"
[ -z "$missing_keep" ] || { say "KEEP のうちリモートにないもの（このスクリプトは消していない）:"; printf '  %s\n' $missing_keep; }
say "完了"
