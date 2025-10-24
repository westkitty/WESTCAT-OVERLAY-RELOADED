import json
import os
import platform
import sys


def main() -> None:
    info = {
        "phase": "1-bootstrap",
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "cwd": os.getcwd(),
        "workspace_note": "Run via VS Codium task or: .venv/bin/python -m app",
    }
    print("BOOTSTRAP_OK")
    print(json.dumps(info, indent=2))


if __name__ == "__main__":
    main()
