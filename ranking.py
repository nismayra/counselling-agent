"""
Ranking and tier utility functions.

Provides tier scoring, multi-tier selection logic, and
the primary sorting function (tier-dominant).
"""

# Fixed tier scores as per spec
TIER_SCORES = {
    "Top": 4,
    "Best": 3,
    "Next-Best": 2,
    "Rest": 1,
}

ALL_TIERS = ["Top", "Best", "Next-Best", "Rest"]


def tier_score(tier: str, selected_tiers: list[str]) -> int:
    """
    Return the tier score for a given tier if it is in the user's selected tiers.
    If the tier is not selected, return 0.
    If multiple tiers are selected, the score is always based on the record's own tier.
    """
    if tier in selected_tiers:
        return TIER_SCORES.get(tier, 0)
    return 0


def compute_sum_of_tiers(
    row,
    college_tiers: list[str],
    branch_tiers: list[str],
    district_tiers: list[str],
) -> int:
    """
    Compute Sum_of_Tiers = College_Tier_Score + Branch_Tier_Score + District_Tier_Score.
    Only tiers that match the user's selection contribute their score.
    """
    c_score = tier_score(row["college_tier"], college_tiers)
    b_score = tier_score(row["branch_tier"], branch_tiers)
    d_score = tier_score(row["district_tier"], district_tiers)
    return c_score + b_score + d_score


def compute_tier_scores_column(
    row,
    college_tiers: list[str],
    branch_tiers: list[str],
    district_tiers: list[str],
) -> dict:
    """Return individual tier scores for display columns."""
    return {
        "college_tier_score": tier_score(row["college_tier"], college_tiers),
        "branch_tier_score": tier_score(row["branch_tier"], branch_tiers),
        "district_tier_score": tier_score(row["district_tier"], district_tiers),
    }
