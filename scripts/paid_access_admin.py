"""Operator commands for access codes: issue a code, list PCs, stop a PC.

Run on the operator's own PC. The administrator token is read from
CYTELLECT_ADMIN_TOKEN or asked for without echo; it is never printed or saved.

    python scripts/paid_access_admin.py issue --label "研究室PC-1" [--hours 24]
    python scripts/paid_access_admin.py list
    python scripts/paid_access_admin.py revoke 0123456789abcdef

The service URL comes from --service, CYTELLECT_PAID_ACCESS_URL or the release default.
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages" / "analysis" / "src"))
from cytellect_analysis import paid_access  # noqa: E402


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


OPENER = urllib.request.build_opener(_NoRedirect)


def call(service: str, path: str, token: str, body: dict | None = None) -> dict:
    request = urllib.request.Request(service + path, data=json.dumps(body or {}).encode("utf-8"), method="POST",
                                     headers={"authorization": f"Bearer {token}", "content-type": "application/json"})
    try:
        with OPENER.open(request, timeout=30) as response:
            return json.loads(response.read(1_000_000))
    except urllib.error.HTTPError as error:
        try:
            code = json.loads(error.read(4096)).get("code", "")
        except (ValueError, AttributeError):
            code = ""
        raise SystemExit(f"拒否されました（HTTP {error.code} {code}）。管理者トークンと接続先を確認してください。") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise SystemExit("サービスに接続できませんでした。接続先とネットワークを確認してください。") from None


def when(milliseconds: int | None) -> str:
    return "" if milliseconds is None else datetime.fromtimestamp(milliseconds / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--service", default=None)
    commands = parser.add_subparsers(dest="command", required=True)
    issue = commands.add_parser("issue", help="1回だけ使える利用コードを発行する")
    issue.add_argument("--label", default="", help="PCの呼び名（研究者名や画像の内容は入れない）")
    issue.add_argument("--hours", type=int, default=24, help="有効時間（1〜168）")
    commands.add_parser("list", help="登録済みのPCと今月の利用数")
    revoke = commands.add_parser("revoke", help="PCの利用を止める")
    revoke.add_argument("device_id")
    args = parser.parse_args(argv)
    service = paid_access.validate_service(args.service) if args.service else paid_access.default_service()
    if not service:
        raise SystemExit("接続先が設定されていません。--service で指定してください。")
    token = os.environ.get("CYTELLECT_ADMIN_TOKEN") or getpass.getpass("管理者トークン: ")
    if args.command == "issue":
        query = urllib.parse.urlencode({"hours": max(1, min(168, args.hours)), **({"label": args.label} if args.label else {})})
        value = call(service, f"/v1/admin/invitations?{query}", token)
        print(f"利用コード（{value['expires_in_hours']} 時間有効、1回限り）:")
        print(value["invitation"])
        print("このコードを研究者に渡してください。作業一覧の「有料機能」に貼り付けると有効になります。")
    elif args.command == "list":
        value = call(service, "/v1/admin/devices", token)
        print(f"{value['month']} の利用数")
        for device in value["devices"]:
            state = f"停止 {when(device['revoked_at'])}" if device["revoked_at"] else "利用中"
            print(f"{device['id']}  {device['label'] or '(名前なし)'}  登録 {when(device['created_at'])}  {state}  "
                  f"Cellpose {device['cellpose_fields']} 視野  解析案 {device['proposals']} 回")
    else:
        value = call(service, "/v1/admin/devices/revoke", token, {"id": args.device_id})
        print(f"{value['revoked']} の利用を止めました。")


if __name__ == "__main__":
    main()
