"""Command-line entry point for the experiment runner."""

from __future__ import annotations

import argparse

from .runner import default_config, preflight, replay, run, workflow
from .web_demo import serve
from .video_assets import render_assets


def main() -> int:
    parser = argparse.ArgumentParser(prog="yc_hack")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("preflight", "run"):
        subparser = subparsers.add_parser(name)
        subparser.add_argument("--config", default=default_config())
        if name == "run":
            subparser.add_argument("--events")
            subparser.add_argument("--mode", choices=("pull", "push"), default="pull")
    replay_parser = subparsers.add_parser("replay")
    replay_parser.add_argument("--events", required=True)
    web_parser = subparsers.add_parser("web")
    web_parser.add_argument("--events", required=True)
    web_parser.add_argument("--host", default="127.0.0.1")
    web_parser.add_argument("--port", type=int, default=8765)
    web_parser.add_argument("--config", default=default_config(), help="enables Start live demo in the browser")
    workflow_parser = subparsers.add_parser("workflow")
    workflow_parser.add_argument("--config", default=default_config())
    workflow_parser.add_argument("--events")
    workflow_parser.add_argument("--resolution", help="JSON file containing explicit user resolutions")
    assets_parser = subparsers.add_parser("video-assets")
    assets_parser.add_argument("--events", required=True)
    assets_parser.add_argument("--output", default=".runtime/video-assets")
    args = parser.parse_args()
    if args.command == "preflight":
        return preflight(args.config)
    if args.command == "run":
        return run(args.config, args.events, args.mode)
    if args.command == "web":
        serve(args.events, args.host, args.port, args.config)
        return 0
    if args.command == "workflow":
        return workflow(args.config, args.events, args.resolution)
    if args.command == "video-assets":
        try:
            assets = render_assets(args.events, args.output)
        except (OSError, ValueError, RuntimeError) as error:
            print(f"video_assets_error={error}")
            return 2
        print(f"video_assets={args.output}")
        for asset in assets:
            print(f"asset={asset}")
        return 0
    return replay(args.events)


if __name__ == "__main__":
    raise SystemExit(main())
