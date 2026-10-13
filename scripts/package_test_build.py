"""Package tracked source and the compiled frontend; never include local state."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/raw/reclaim-local-test-build.zip")
    args = parser.parse_args()
    if not (ROOT / "dist/index.html").is_file():
        parser.error("Run npm run build first.")
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    files = [ROOT / path for path in tracked if path]
    files += sorted(path for path in (ROOT / "dist").rglob("*") if path.is_file())
    entries = {}
    for path in files:
        relative = path.relative_to(ROOT).as_posix()
        if path.is_symlink() or not path.is_file():
            parser.error(f"Refusing a missing file or symlink: {relative}")
        if (path.name == ".env" or (path.name.startswith(".env.") and path.name != ".env.example")
                or path.name.endswith((".db", ".db-wal", ".db-shm", ".pyc"))
                or relative.startswith(("artifacts/raw/", ".local-build/", ".venv/", "node_modules/"))):
            parser.error(f"Refusing local data: {relative}")
        entries[relative] = path.read_bytes()
    manifest = {
        "format": "reclaim-local-test-build-v1",
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip(),
        "working_tree_clean": not subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT).strip(),
        "requires": "Python 3.12 or later; internet for the first dependency install",
        "default_mode": "Labelled deterministic parser and simulated payments",
        "files": {name: hashlib.sha256(data).hexdigest() for name, data in sorted(entries.items())},
    }
    entries["BUILD-MANIFEST.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(entries.items()):
            archive.writestr("reclaim-local-test-build/" + name, data)
    with zipfile.ZipFile(args.output) as archive:
        assert archive.testzip() is None
    print(json.dumps({"path": str(args.output.resolve()), "files": len(entries), "bytes": args.output.stat().st_size,
                      "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
                      "source_commit": manifest["source_commit"], "working_tree_clean": manifest["working_tree_clean"]}))


if __name__ == "__main__":
    main()
