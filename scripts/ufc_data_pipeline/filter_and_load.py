import json
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path("./data")


def build_fighter_appearance_map(all_fights: list[dict]) -> dict[str, int]:
    """
    Count UFC appearances per fighter.
    Returns: { "Conor McGregor": 27, "Jon Jones": 28, ... }
    """
    appearances: dict[str, int] = defaultdict(int)
    for fight in all_fights:
        if fight.get('fighter_a_name'):
            appearances[fight['fighter_a_name']] += 1
        if fight.get('fighter_b_name'):
            appearances[fight['fighter_b_name']] += 1
    return dict(appearances)


def filter_eligible_fighters(
    all_fights: list[dict],
    min_appearances: int = 5,
) -> tuple[set[str], dict[str, int]]:
    """
    Returns:
    - eligible_fighters: set of names with min_appearances+ appearances
    - appearance_map: full count for all fighters
    """
    appearance_map = build_fighter_appearance_map(all_fights)
    eligible = {
        name for name, count in appearance_map.items()
        if count >= min_appearances
    }

    print(f"Total unique fighters: {len(appearance_map)}")
    print(f"Fighters with {min_appearances}+ appearances: {len(eligible)}")
    # Expected: ~800-1,100 eligible fighters

    return eligible, appearance_map


def filter_fights_for_eligible(
    all_fights: list[dict],
    eligible_fighters: set[str],
) -> list[dict]:
    """
    Keep fights where BOTH fighters have 5+ appearances (primary training set)
    and fights where ONE fighter is eligible (used for FPS scoring).
    Annotates each fight with an 'eligibility' key ('both' | 'one').
    Input dicts are not mutated — copies are made.
    """
    both_eligible: list[dict] = []
    one_eligible: list[dict] = []

    for fight in all_fights:
        a = fight.get('fighter_a_name') or ''
        b = fight.get('fighter_b_name') or ''
        a_eligible = bool(a) and a in eligible_fighters
        b_eligible = bool(b) and b in eligible_fighters

        if a_eligible and b_eligible:
            both_eligible.append({**fight, 'eligibility': 'both'})
        elif a_eligible or b_eligible:
            one_eligible.append({**fight, 'eligibility': 'one'})

    print(f"Fights with BOTH fighters eligible: {len(both_eligible)}")
    print(f"Fights with ONE fighter eligible:  {len(one_eligible)}")
    # Expected: ~2,500-3,000 both-eligible fights
    # These become the primary simulation training set

    return both_eligible + one_eligible


if __name__ == "__main__":
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    all_fights: list[dict] = json.loads((DATA_DIR / "ufc_all_fights.json").read_text())
    eligible_fighters, appearance_map = filter_eligible_fighters(all_fights)

    (DATA_DIR / "eligible_fighters.json").write_text(
        json.dumps(sorted(eligible_fighters), indent=2)
    )

    filtered_fights = filter_fights_for_eligible(all_fights, eligible_fighters)
    (DATA_DIR / "filtered_fights.json").write_text(
        json.dumps(filtered_fights, indent=2)
    )

    print(f"Saved {len(eligible_fighters)} eligible fighters → data/eligible_fighters.json")
    print(f"Saved {len(filtered_fights)} filtered fights → data/filtered_fights.json")
