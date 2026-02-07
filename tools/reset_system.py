"""
System Reset Tool for AI Life OS.
CAUTION: This will delete all your data and restart the Steward from scratch.
"""
import os
import shutil
import subprocess
import time
import sys
from pathlib import Path

# Paths to clean (relative to project root)
DATA_DIR = Path("data")
TARGETS = [
    DATA_DIR / "event_log.jsonl",
    DATA_DIR / "character_state.json",
    DATA_DIR / "goal_registry.json",
    DATA_DIR / "audit_log.jsonl",
    DATA_DIR / "action_queue.json",
    DATA_DIR / "snapshots"  # Directory
]

def kill_blocking_processes():
    """
    Detects and kills python processes that are running from the current project directory.
    Uses wmic to avoid external dependencies like psutil.
    """
    print("\n[Process Check] Scanning for blocking background processes...")
    current_dir = os.getcwd().lower()
    
    # Find python processes with command lines containing the current directory name
    # We use wmic for Windows compatibility without extra deps
    try:
        cmd = 'wmic process where "name=\'python.exe\'" get processid,commandline /format:csv'
        result = subprocess.check_output(cmd, shell=True, text=True)
    except subprocess.CalledProcessError:
        print("⚠️  Could not query processes via WMIC. Skipping process check.")
        return

    blocking_procs = []
    my_pid = os.getpid()

    lines = result.strip().splitlines()
    if len(lines) > 1:
        # header is usually first line
        for line in lines:
            if not line.strip(): continue
            parts = line.split(",")
            if len(parts) >= 2:
                # WMIC CSV format usually: Node,CommandLine,ProcessId
                # But sometimes varies, usually ends with PID. 
                # Let's find the pid and cmdline robustly.
                # standard output: Node, CommandLine, ProcessId
                try:
                    pid = int(parts[-1])
                    cmdline = ",".join(parts[1:-1]) # Join back usually middle parts
                except ValueError:
                    continue
                
                if pid == my_pid:
                    continue

                if "ai_life_os" in cmdline.lower() or "ai_life_os" in current_dir and current_dir in cmdline.lower():
                    blocking_procs.append((pid, cmdline))

    if not blocking_procs:
        print("✅ No blocking project processes found.")
        return

    print(f"\n⚠️  Found {len(blocking_procs)} background processes that might lock files:")
    for pid, cmd in blocking_procs:
        print(f"   [PID {pid}] {cmd[:100]}...")
    
    print("\n🔴 Terminating these processes to release file locks...")

    for pid, _ in blocking_procs:
        try:
            print(f"   Killing PID {pid} (+ tree)...", end=" ")
            # /T terminates child processes as well, important for uvicorn/reloaders
            subprocess.run(f"taskkill /F /T /PID {pid}", shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("✅ Done.")
        except subprocess.CalledProcessError:
            print("❌ Failed.")

    print("waiting 2 seconds for OS to release locks...")
    time.sleep(2)

def list_blocking_processes_only():
    """Helper to just list processes for diagnostics without interaction."""
    print("\n[Diagnostic] Re-scanning for persistent python processes...")
    # ... (simplified version of detection logic or just reuse wmic command) ...
    # To avoid code duplication, we can refactor, but for now let's just run a quick wmic command
    try:
         subprocess.run('wmic process where "name=\'python.exe\'" get processid,commandline', shell=True)
    except:
        pass

def reset_system():
    print("⚠️  WARNING: This will PERMANENTLY DELETE all your data (Goals, visions, history).")
    print("Executing system reset immediately...")

    # First, handle processes
    kill_blocking_processes()

    print("\n[System Reset] Initiating cleanup...")
    
    for target in TARGETS:
        if target.exists():
            deleted = False
            for attempt in range(3):
                try:
                    if target.is_dir():
                        shutil.rmtree(target)
                        print(f"✅ Deleted directory: {target}")
                    else:
                        os.remove(target)
                        print(f"✅ Deleted file: {target}")
                    deleted = True
                    break
                except Exception as e:
                    last_error = e
                    if attempt < 2:
                        time.sleep(1) # wait and retry
                    else:
                        print(f"❌ Failed to delete {target}: {e}")
            
            if not deleted:
                print(f"   (Could not remove {target} after 3 attempts)")
                # Diagnostic help
                if "last_error" in locals() and ("WinError 32" in str(last_error) or "used by another process" in str(last_error)):
                     list_blocking_processes_only()
        else:
            print(f"⚪ Skipped (not found): {target}")

    print("\n[System Reset] Complete. Please restart the backend server.")

if __name__ == "__main__":
    reset_system()
