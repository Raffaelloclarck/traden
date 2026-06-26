#!/usr/bin/env python3
"""Start het web dashboard op http://localhost:8080"""

import argparse

from traden.dashboard.server import run


def main() -> None:
    parser = argparse.ArgumentParser(description="Traden dashboard")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()

    print(f"\n  Dashboard: http://{args.host}:{args.port}\n")
    print("  Tip: run ook 'python main.py --loop' in een andere terminal\n")
    run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
