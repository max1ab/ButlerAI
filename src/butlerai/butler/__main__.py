from __future__ import annotations

import argparse

from .server import ButlerHTTPServer


def main() -> None:
    parser = argparse.ArgumentParser(prog="butlerai-butler", description="Run ButlerAI Butler (HTTP server)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    server = ButlerHTTPServer(host=args.host, port=args.port)
    server.serve_forever()


if __name__ == "__main__":
    main()

