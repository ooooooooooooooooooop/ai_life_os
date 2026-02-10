
from core.event_sourcing import rebuild_state
from core.models import GoalStatus
from collections import Counter

def verify():
    print("Rebuilding state...")
    state = rebuild_state()
    active_goals = [g for g in state["goals"] if g.status == GoalStatus.ACTIVE]

    print(f"Total active goals: {len(active_goals)}")

    titles = [g.title for g in active_goals]
    counts = Counter(titles)

    duplicates = {t: c for t, c in counts.items() if c > 1}

    if duplicates:
        print("\n❌ Verification FAILED. Duplicates found in ACTIVE goals:")
        for t, c in duplicates.items():
            print(f"  {c}x: {t}")
        exit(1)
    else:
        print("\n✅ Verification PASSED. No duplicates in ACTIVE goals.")

    # Also check if normalization worked on the "Option" ones
    # We expect "选项1: ..." to be GONE, replaced by clean titles if any were kept?
    # Actually, the cleanup kept the FIRST one. The first one likely HAD the prefix "选项1: ...".
    # My cleanup script did NOT rename the goals, it just removed duplicates.
    # So the remaining one might still have the ugly name "选项1: ...".
    # This is partially solved. Ideally we should also RENAME the remaining goal to be clean.

    print("\nChecking for un-normalized titles...")
    ugly_titles = [t for t in titles if "Option" in t or "选项" in t]
    if ugly_titles:
        print(
            f"⚠️ Warning: {len(ugly_titles)} titles still look un-normalized "
            "(but might not be duplicates):"
        )
        for t in ugly_titles:
            print(f"  - {t}")
    else:
        print("All titles look clean (no 'Option'/'选项' prefixes).")

if __name__ == "__main__":
    verify()
