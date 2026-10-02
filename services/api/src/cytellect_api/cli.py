import argparse
import json
from pathlib import Path
from .config import Settings
from .db import Store

def main():
    parser=argparse.ArgumentParser(prog="cytellect")
    sub=parser.add_subparsers(dest="command",required=True)
    invite=sub.add_parser("invite")
    invite.add_argument("--hours",type=int,default=24)
    sub.add_parser("cleanup")
    sub.add_parser("openapi").add_argument("--output",type=Path,required=True)
    sub.add_parser("serve").add_argument("--port",type=int,default=8000)
    args=parser.parse_args()
    settings=Settings.from_env()
    if args.command=="invite":
        if not 1<=args.hours<=168:
            parser.error("hours must be 1..168")
        # The operator receives this once. Never send stdout to central logs.
        print(Store(settings.data_dir).invite(args.hours*3600))
    elif args.command=="cleanup":
        from cytellect_worker.main import cleanup
        cleanup(Store(settings.data_dir))
    elif args.command=="openapi":
        from .app import create_app
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(create_app(settings).openapi(),indent=2),encoding="utf-8")
    else:
        import uvicorn
        uvicorn.run("cytellect_api.app:app",host="127.0.0.1",port=args.port,access_log=False)

if __name__=="__main__":
    main()
