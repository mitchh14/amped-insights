"""Build the static browser demo into a folder that any static host can serve.

The demo is the normal web page plus demo/demo.js, which runs the Python
core in the browser with Pyodide. Nothing is copied by hand: the page and the
Python files come straight from anchor/, so the demo always matches the repo.

Usage: python scripts/build_demo.py [out_dir] [--pyodide-url URL]
"""

import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Only the stdlib parts of the package. The MCP server needs the mcp SDK and has no use in a browser.
PY_FILES = ["__init__.py", "core.py", "api.py", "seed.py"]


def build(out: Path, pyodide_url: str | None) -> None:
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    config = {"pyodideUrl": pyodide_url} if pyodide_url else {}
    head = (
        f"<script>window.ANCHOR_DEMO = {json.dumps(config)};</script>\n"
        '<link rel="stylesheet" href="demo.css">\n'
        '<script src="demo.js"></script>\n'
        "</head>"
    )
    page = (ROOT / "anchor/static/index.html").read_text()
    assert page.count("</head>") == 1, "index.html should have exactly one </head>"
    (out / "index.html").write_text(page.replace("</head>", head))

    for name in ["demo.js", "demo.css"]:
        shutil.copy(ROOT / "demo" / name, out / name)
    src = {name: (ROOT / "anchor" / name).read_text() for name in PY_FILES}
    (out / "anchor-src.json").write_text(json.dumps(src))
    (out / ".nojekyll").write_text("")
    print(f"Built demo in {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out", nargs="?", default="_site")
    parser.add_argument("--pyodide-url", help="where to load Pyodide from (default: the jsDelivr CDN)")
    args = parser.parse_args()
    build(Path(args.out), args.pyodide_url)
