#!/usr/bin/env python3
"""Copy /shared modules into the services that use them.

    python scripts/sync_shared.py          # copy
    python scripts/sync_shared.py --check  # exit 1 if any copy drifted (CI)
"""
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SHARED = ROOT / "shared"

# service -> shared modules it needs
USES = {
    "rag": ["textutil.py", "refs.py"],
    "ingest": ["textutil.py", "refs.py", "secrets_redact.py"],
    "orchestrator": ["textutil.py", "refs.py", "secrets_redact.py"],
    "eval": ["textutil.py", "refs.py"],
}


def main(check: bool) -> int:
    drift = []
    for service, files in USES.items():
        dest_dir = ROOT / "services" / service / "app"
        dest_dir.mkdir(parents=True, exist_ok=True)
        for name in files:
            src, dst = SHARED / name, dest_dir / name
            if check:
                if not dst.exists() or dst.read_bytes() != src.read_bytes():
                    drift.append(str(dst.relative_to(ROOT)))
            else:
                shutil.copyfile(src, dst)
    if check and drift:
        print("shared modules out of sync (run: python scripts/sync_shared.py):")
        for d in drift:
            print("  ", d)
        return 1
    print("shared modules in sync" if check else "shared modules copied")
    return 0


if __name__ == "__main__":
    sys.exit(main("--check" in sys.argv))
