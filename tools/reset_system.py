"""
System reset tool for AI Life OS.
Deletes runtime data files and snapshots.
"""
import os
import shutil
import subprocess
import time
from pathlib import Path

from core.paths import DATA_DIR

TARGETS = [
    DATA_DIR / "event_log.jsonl",
    DATA_DIR / "character_state.json",
    DATA_DIR / "goal_registry.json",
    DATA_DIR / "audit_log.jsonl",
    DATA_DIR / "action_queue.json",
    DATA_DIR / "snapshots",
]


def kill_blocking_processes() -> None:
    """
    Detect and kill python processes that may lock runtime files on Windows.
    """
    print("\n[Process Check] scanning for blocking background processes...")
    current_dir = os.getcwd().lower()

    try:
        cmd = 'wmic process where "name=\'python.exe\'" get processid,commandline /format:csv'
        result = subprocess.check_output(cmd, shell=True, text=True)
    except subprocess.CalledProcessError:
        print("[warn] could not query processes via WMIC; skip process check.")
        return

    blocking_procs = []
    my_pid = os.getpid()

    for line in result.strip().splitlines():
        if not line.strip():
            continue
        parts = line.split(",")
        if len(parts) < 2:
            continue
        try:
            pid = int(parts[-1])
            cmdline = ",".join(parts[1:-1])
        except ValueError:
            continue

        if pid == my_pid:
            continue
        if "ai_life_os" in cmdline.lower() or (current_dir and current_dir in cmdline.lower()):
            blocking_procs.append((pid, cmdline))

    if not blocking_procs:
        print("[ok] no blocking project processes found.")
        return

    print(f"[warn] found {len(blocking_procs)} process(es) that may lock files.")
    for pid, cmd in blocking_procs:
        print(f"  pid={pid} cmd={cmd[:120]}...")

    for pid, _ in blocking_procs:
        try:
            subprocess.run(
                f"taskkill /F /T /PID {pid}",
                shell=True,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            print(f"[ok] killed pid {pid}")
        except subprocess.CalledProcessError:
            print(f"[warn] failed to kill pid {pid}")

    time.sleep(2)


def reset_system() -> None:
    print("[warning] this will permanently delete runtime data.")
    print(f"[info] data directory: {DATA_DIR}")

    kill_blocking_processes()
    print("\n[reset] cleaning runtime files...")

    for target in TARGETS:
        if not target.exists():
            print(f"[skip] not found: {target}")
            continue

        deleted = False
        last_error = None
        for attempt in range(3):
            try:
                if target.is_dir():
                    shutil.rmtree(target)
                    print(f"[ok] deleted directory: {target}")
                else:
                    target.unlink()
                    print(f"[ok] deleted file: {target}")
                deleted = True
                break
            except Exception as e:  # noqa: BLE001
                last_error = e
                if attempt < 2:
                    time.sleep(1)

        if not deleted:
            print(f"[error] failed to delete {target}: {last_error}")

    print("\n[reset] complete. restart backend service.")


if __name__ == "__main__":
    reset_system()
