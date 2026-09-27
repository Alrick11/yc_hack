"""Backward-compatible entry point for running the configured experiment."""

from __future__ import annotations

import argparse

from .runner import default_config, run


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=default_config())
    parser.add_argument("--events")
    parser.add_argument("--mode", choices=("pull", "push"), default="pull")
    args = parser.parse_args()
    return run(args.config, args.events, args.mode)


if __name__ == "__main__":
    raise SystemExit(main())
