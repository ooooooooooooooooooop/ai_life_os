import sys
from pathlib import Path
import logging

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.models import UserProfile  # noqa: E402
from core.goal_generator import GoalGenerator  # noqa: E402
from core.blueprint import Blueprint  # noqa: E402

# Setup simple logging to console
logging.basicConfig(level=logging.INFO)

def main():
    print(">>> Initializing Blueprint...")
    blueprint = Blueprint()
    print(f"Loaded principles: {[p['name'] for p in blueprint.principles]}")

    generator = GoalGenerator(blueprint)

    # Mock Profile
    profile = UserProfile(
        occupation="Software Engineer", # original occupation
        focus_area="AI & Automation",
        daily_hours="3h",
        preferences="Likes heavy lifting, dislikes cardio. Interested in philosophy."
    )

    print("\n>>> Generating Goals for Profile:")
    print(f"Occupation: {profile.occupation}")
    print(f"Focus: {profile.focus_area}")
    print(f"Preferences: {profile.preferences}")

    goals_with_scores = generator.generate_candidates(profile, n=3)

    print("\n>>> Generated Results:")
    for i, (goal, score) in enumerate(goals_with_scores):
        print(f"\nGoal #{i+1}: {goal.title} [{goal.id}]")
        print(f"Category/Tags: {getattr(goal, 'tags', 'N/A')}")
        print(f"Description: {goal.description}")
        print(f"Target Level: {goal.target_level}")
        print(f"Blueprint Score: {score.score:.2f} (Passed: {score.passed})")
        print("Breakdown:")
        for k, v in score.breakdown.items():
            print(f"  - {k}: {v}")

if __name__ == "__main__":
    main()
