from __future__ import annotations

import json
import sys
from pathlib import Path

from axis_api.main import create_app


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: export_openapi.py <output-path>", file=sys.stderr)
        return 2

    output_path = Path(sys.argv[1])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(create_app().openapi(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
