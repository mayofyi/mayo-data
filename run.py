"""
Mayo Data Pipeline — main entry point.
Runs the full pipeline: collect → score → output.
"""

from dotenv import load_dotenv

load_dotenv()

import connectors.instagram as instagram


def report(data: dict) -> None:
    profile = data["profile"]
    media = data["media"]
    insights = data["insights"]
    er = data["engagement_rate"]

    followers = profile.get("followers_count", 0)
    reach = insights.get("reach", 0)
    has_saves = any(p.get("saved_count") for p in media)
    has_shares = any(v for v in data.get("shares", {}).values())

    print("\n" + "═" * 50)
    print(f"  {profile.get('name', '').upper()}")
    print("═" * 50)

    print(f"\n  Followers       {followers:,}                  [Fully Verified]")

    if reach:
        print(f"  Reach           {reach:,}                  [Fully Verified]")
    else:
        print(f"  Reach           BLOCKED — needs new token with insights permission")

    formula_parts = ["likes×1", "comments×2"]
    if has_saves:
        formula_parts.append("saves×3")
    if has_shares:
        formula_parts.append("shares×4")
    missing = []
    if not has_saves:
        missing.append("saves")
    if not has_shares:
        missing.append("shares")

    print(f"\n  Weighted ER     {er}%                [Fully Verified]")
    print(f"                  formula: {' + '.join(formula_parts)}")
    if missing:
        print(f"                  excluded (needs insights permission): {', '.join(missing)}")

    print(f"\n  CCE             BLOCKED — needs cross-channel data (Substack not connected)")
    print(f"  Total Reach     BLOCKED — needs insights permission + cross-channel data")
    print(f"  Network Mult.   BLOCKED — needs member list + third-party verification")
    print(f"  Cultural Impact BLOCKED — needs press monitoring + Mayo review")
    print(f"  Match Score     — (no active brief)")

    print(f"\n  Active Members  [not set — enter manually]         [community-reported]")

    print(f"\n  Website         {profile.get('website') or '—'}")
    print(f"  Bio             {(profile.get('biography') or '')[:80]}")

    print("\n" + "═" * 50 + "\n")


def main():
    print("Mayo Data Pipeline")
    print("------------------")

    data = instagram.collect()
    report(data)


if __name__ == "__main__":
    main()
