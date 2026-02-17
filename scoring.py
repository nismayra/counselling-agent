"""
Weighted scoring engine.

Converts ranks to scores and computes the weighted final score
based on user-provided weightages for district, department, branch, and college.
"""

import pandas as pd
from ranking import (
    tier_score,
    TIER_SCORES,
    ALL_TIERS,
)


def normalize_weights(
    district_w: float, department_w: float, branch_w: float, college_w: float
) -> tuple[float, float, float, float]:
    """Normalize user-input percentage weights (0-100) to sum to 1.0."""
    total = district_w + department_w + branch_w + college_w
    if total == 0:
        return 0.25, 0.25, 0.25, 0.25
    return district_w / total, department_w / total, branch_w / total, college_w / total


def rank_to_score(rank: int, max_rank: int) -> int:
    """Convert rank to score: rank_score = (max_rank + 1) - rank. Higher score = better."""
    return max_rank + 1 - rank


def compute_final_scores(
    df: pd.DataFrame,
    district_w: float,
    department_w: float,
    branch_w: float,
    college_w: float,
) -> pd.Series:
    """
    Compute weighted final score for each row.

    final_score = (district_rank_score * district_weight) +
                  (department_rank_score * department_weight) +
                  (branch_rank_score * branch_weight) +
                  (college_rank_score * college_weight)
    """
    d_w, dep_w, b_w, c_w = normalize_weights(district_w, department_w, branch_w, college_w)

    # Compute max ranks for score conversion
    d_max = df["district_rank"].max()
    dep_max = df["department_rank"].max()
    b_max = df["branch_rank"].max()
    c_max = df["college_rank"].max()

    # rank_score = (max_rank + 1) - rank
    d_score = (d_max + 1 - df["district_rank"])
    dep_score = (dep_max + 1 - df["department_rank"])
    b_score = (b_max + 1 - df["branch_rank"])
    c_score = (c_max + 1 - df["college_rank"])

    return (d_score * d_w) + (dep_score * dep_w) + (b_score * b_w) + (c_score * c_w)


def apply_tier_filtering_and_scoring(
    df: pd.DataFrame,
    college_tiers: list[str],
    branch_tiers: list[str],
    district_tiers: list[str],
    district_w: float,
    department_w: float,
    branch_w: float,
    college_w: float,
) -> pd.DataFrame:
    """
    Full scoring pipeline:
    1. Compute individual tier scores based on user's tier selections
    2. Compute sum_of_tiers (primary sort key)
    3. Compute weighted final_score (secondary sort key)
    4. Sort by tier-dominant logic
    5. Assign choose_order
    """
    result = df.copy()

    # Tier scores per category
    result["college_tier_score"] = result["college_tier"].apply(
        lambda t: tier_score(t, college_tiers)
    )
    result["branch_tier_score"] = result["branch_tier"].apply(
        lambda t: tier_score(t, branch_tiers)
    )
    result["district_tier_score"] = result["district_tier"].apply(
        lambda t: tier_score(t, district_tiers)
    )

    # Sum of tiers (primary sorting key)
    result["sum_of_tiers"] = (
        result["college_tier_score"]
        + result["branch_tier_score"]
        + result["district_tier_score"]
    )

    # Weighted final score (secondary sorting key)
    result["final_score"] = compute_final_scores(
        result, district_w, department_w, branch_w, college_w
    )
    result["final_score"] = result["final_score"].round(2)

    # Tier-dominant sorting (STRICT order from spec):
    # 1. sum_of_tiers DESC
    # 2. final_score DESC
    # 3. OC Cutoff DESC
    # 4. global ranks ASC (college_rank as tiebreaker)
    result = result.sort_values(
        by=["sum_of_tiers", "final_score", "Catogery OC Cutoff", "college_rank"],
        ascending=[False, False, False, True],
    ).reset_index(drop=True)

    # choose_order = row number after sorting (1-based)
    result["choose_order"] = range(1, len(result) + 1)

    return result
