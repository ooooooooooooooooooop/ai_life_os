"""
Migrate AI Life OS runtime data to a new directory.
"""
import argparse
import shutil
from pathlib import Path

from core.paths import PROJECT_ROOT


def migrate_data(src: Path, dest: Path, overwrite: bool = False) -> None:
    src = src.resolve()
    dest = dest.resolve()

    if not src.exists():
        print(f"[error] source does not exist: {src}")
        return

    if src == dest:
        print("[skip] source and destination are the same.")
        return

    dest.mkdir(parents=True, exist_ok=True)
    moved = 0
    skipped = 0

    for item in src.iterdir():
        target = dest / item.name
        if target.exists() and not overwrite:
            print(f"[skip] exists: {target}")
            skipped += 1
            continue

        if item.is_dir():
            if target.exists() and overwrite:
                shutil.rmtree(target)
            shutil.copytree(item, target, dirs_exist_ok=overwrite)
        else:
            if target.exists() and overwrite:
                target.unlink()
            shutil.copy2(item, target)
        moved += 1
        print(f"[ok] copied: {item.name}")

    print(f"\n[done] copied {moved} item(s), skipped {skipped} item(s)")
    print(f"[next] set AI_LIFE_OS_DATA_DIR={dest}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate runtime data directory.")
    parser.add_argument(
        "--src",
        type=Path,
        default=PROJECT_ROOT / "data",
        help="source data directory (default: ./data)",
    )
    parser.add_argument("--dest", type=Path, required=True, help="destination data directory")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="overwrite existing files/directories at destination",
    )
    args = parser.parse_args()

    migrate_data(args.src, args.dest, overwrite=args.overwrite)


if __name__ == "__main__":
    main()
