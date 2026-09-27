"""Command-line entry point for the experiment runner."""

from __future__ import annotations

import argparse

from .runner import default_config, preflight, replay, run


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
    args = parser.parse_args()
    if args.command == "preflight":
        return preflight(args.config)
    if args.command == "run":
        return run(args.config, args.events, args.mode)
    return replay(args.events)


if __name__ == "__main__":
    raise SystemExit(main())
