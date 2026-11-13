"""Compatibility entry point. The approved v0.6 UI supersedes split-pane checks."""
import asyncio
import argparse
from pathlib import Path
from verify_research_v06_browser import verify

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8010")
    parser.add_argument("--output", type=Path, default=Path("/tmp/oireachtasontology/research-v06"))
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    asyncio.run(verify(args.url.rstrip("/"), args.output, args.resume))
