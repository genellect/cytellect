import argparse
import json
import sys
from pathlib import Path

from .config import Settings, configure_private_tmp
from .db import Store


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "local":
        from .local import main as local_main

        return local_main(sys.argv[2:])
    parser = argparse.ArgumentParser(prog="cytellect")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("local", help="Start the private loopback UI and supervised worker")
    invite = sub.add_parser("invite")
    invite.add_argument("--hours", type=int, default=24)
    sub.add_parser("cleanup")
    schema = sub.add_parser("openapi")
    schema.add_argument("--output", type=Path, required=True)
    schema.add_argument("--recipe-defaults", type=Path)
    serve = sub.add_parser("serve")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--host", default="127.0.0.1")
    sub.add_parser("migrate")
    args = parser.parse_args()
    settings = Settings.from_env()
    configure_private_tmp(settings)
    if args.command == "invite":
        if not 1 <= args.hours <= 168:
            parser.error("hours must be 1..168")
        # The operator receives this once. Never send stdout to central logs.
        print(Store(settings.data_dir).invite(args.hours * 3600))
    elif args.command == "migrate":
        Store(settings.data_dir)
    elif args.command == "cleanup":
        from cytellect_worker.main import cleanup

        cleanup(Store(settings.data_dir))
    elif args.command == "openapi":
        from .app import create_app

        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(create_app(settings).openapi(), indent=2), encoding="utf-8")
        if args.recipe_defaults:
            from cytellect_analysis.contracts import Recipe

            args.recipe_defaults.parent.mkdir(parents=True, exist_ok=True)
            args.recipe_defaults.write_text(Recipe().model_dump_json(indent=2) + "\n", encoding="utf-8")
    else:
        import uvicorn

        uvicorn.run(
            "cytellect_api.app:create_app", factory=True, host=args.host, port=args.port, access_log=False
        )


if __name__ == "__main__":
    main()
