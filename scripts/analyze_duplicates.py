
import json
from collections import Counter
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
EVENT_LOG_PATH = DATA_DIR / "event_log.jsonl"

def analyze():
    if not EVENT_LOG_PATH.exists():
        print(f"File not found: {EVENT_LOG_PATH}")
        return

    goals = []
    goal_titles = []
    
    with open(EVENT_LOG_PATH, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
                if event["type"] == "goal_created":
                    goal = event["payload"]["goal"]
                    goals.append(goal)
                    goal_titles.append(goal["title"])
            except Exception as e:
                print(f"Error parsing line {line_num}: {e}")

    print(f"Total goals created: {len(goals)}")
    
    title_counts = Counter(goal_titles)
    
    print("\n--- Top Duplicates ---")
    for title, count in title_counts.most_common(10):
        if count > 1:
            print(f"{count}x: {title}")
            
    print("\n--- 'Option' Goals ---")
    option_goals = [t for t in goal_titles if "选项" in t or "Option" in t]
    option_counts = Counter(option_goals)
    for title, count in option_counts.most_common(10):
         print(f"{count}x: {title}")

if __name__ == "__main__":
    analyze()
