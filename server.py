from __future__ import annotations

import argparse
import threading
import webbrowser
from pathlib import Path

from backend.api import create_server


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the SIH26227 TerraTrace EO prototype")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent
    server = create_server(project_root, args.host, args.port)
    url = f"http://{args.host}:{args.port}/"
    print("\nTerraTrace EO · SIH26227")
    print(f"Local prototype: {url}")
    print("Network services are not required. Press Ctrl+C to stop.\n")
    if not args.no_browser:
        threading.Timer(0.7, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping TerraTrace EO.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

