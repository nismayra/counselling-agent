"""
Database schema, data loading, and precomputation module.

Loads CSV data into SQLite, computes global ranks and tiers,
and stores them for use by the scoring and UI layers.
"""

import os
import pandas as pd
from sqlalchemy import create_engine, text

DB_PATH = "counselling.db"
DATA_DIR = os.path.join(os.path.dirname(__file__), "Data")


def get_engine(db_path: str = DB_PATH):
    return create_engine(f"sqlite:///{db_path}", echo=False)


def load_csvs(year: str = "2020") -> dict[str, pd.DataFrame]:
    """Load all CSV files for a given year into DataFrames."""
    year_dir = os.path.join(DATA_DIR, year)

    districts = pd.read_csv(os.path.join(year_dir, "Districts.csv"))
    colleges = pd.read_csv(os.path.join(year_dir, "Colleges-info.csv"))
    branches = pd.read_csv(os.path.join(year_dir, "Branches.csv"))
    cutoff = pd.read_csv(os.path.join(year_dir, "Cutoff.csv"))

    # Standardize column names (strip whitespace)
    for df in [districts, colleges, branches, cutoff]:
        df.columns = df.columns.str.strip()

    # Add year column to cutoff for future multi-year support
    cutoff["Year"] = int(year)

    return {
        "districts": districts,
        "colleges": colleges,
        "branches": branches,
        "cutoff": cutoff,
    }


def compute_ranks_and_tiers(cutoff: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """
    Compute global dense ranks and quartile tiers for districts,
    departments, branches, and colleges based on max OC cutoff.

    Ranking direction: Higher OC cutoff = better (Rank 1 = highest cutoff).
    Tier assignment: Top 25% = 'Top', next 25% = 'Best', next 25% = 'Next-Best', bottom 25% = 'Rest'.
    """

    def _rank_and_tier(group_col: str, rank_prefix: str) -> pd.DataFrame:
        """Group by group_col, get max cutoff, dense rank descending, assign tier."""
        agg = (
            cutoff.groupby(group_col)["Catogery OC Cutoff"]
            .max()
            .reset_index()
            .rename(columns={"Catogery OC Cutoff": f"{rank_prefix}_max_cutoff"})
        )
        # Dense rank: rank 1 = highest cutoff
        agg[f"{rank_prefix}_rank"] = (
            agg[f"{rank_prefix}_max_cutoff"]
            .rank(method="dense", ascending=False)
            .astype(int)
        )
        # Assign tiers based on rank percentile
        max_rank = agg[f"{rank_prefix}_rank"].max()
        agg[f"{rank_prefix}_tier"] = agg[f"{rank_prefix}_rank"].apply(
            lambda r: _tier_label(r, max_rank)
        )
        return agg

    results = {
        "district_ranks": _rank_and_tier("District ID", "district"),
        "department_ranks": _rank_and_tier("Department ID", "department"),
        "branch_ranks": _rank_and_tier("Branch Code", "branch"),
        "college_ranks": _rank_and_tier("College code", "college"),
    }
    return results


def _tier_label(rank: int, max_rank: int) -> str:
    """
    Assign tier based on rank position within the total count.
    Top 25% of ranks → 'Top', next 25% → 'Best', next 25% → 'Next-Best', rest → 'Rest'.
    """
    percentile = rank / max_rank
    if percentile <= 0.25:
        return "Top"
    elif percentile <= 0.50:
        return "Best"
    elif percentile <= 0.75:
        return "Next-Best"
    else:
        return "Rest"


def build_master_table(
    cutoff: pd.DataFrame,
    districts: pd.DataFrame,
    colleges: pd.DataFrame,
    branches: pd.DataFrame,
    ranks: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """
    Join cutoff data with all reference tables and precomputed ranks
    to produce the master table used by the UI.
    """
    master = cutoff.copy()

    # Merge district names
    master = master.merge(districts, on="District ID", how="left")

    # Merge college names
    master = master.merge(colleges, on="College code", how="left", suffixes=("", "_col"))
    # Drop duplicate District ID from colleges merge if present
    if "District ID_col" in master.columns:
        master.drop(columns=["District ID_col"], inplace=True)

    # Merge branch info
    master = master.merge(branches, on="Branch Code", how="left", suffixes=("", "_br"))
    if "Department ID_br" in master.columns:
        master.drop(columns=["Department ID_br"], inplace=True)

    # Merge ranks
    master = master.merge(ranks["district_ranks"], on="District ID", how="left")
    master = master.merge(ranks["department_ranks"], on="Department ID", how="left")
    master = master.merge(ranks["branch_ranks"], on="Branch Code", how="left")
    master = master.merge(ranks["college_ranks"], on="College code", how="left")

    return master


def init_db(year: str = "2020", db_path: str = DB_PATH) -> pd.DataFrame:
    """
    Full pipeline: load CSVs → compute ranks/tiers → build master table → store in SQLite.
    Returns the master DataFrame.
    """
    data = load_csvs(year)
    ranks = compute_ranks_and_tiers(data["cutoff"])

    master = build_master_table(
        data["cutoff"],
        data["districts"],
        data["colleges"],
        data["branches"],
        ranks,
    )

    # Store to SQLite
    engine = get_engine(db_path)
    master.to_sql("master", engine, if_exists="replace", index=False)
    data["districts"].to_sql("districts", engine, if_exists="replace", index=False)
    data["colleges"].to_sql("colleges", engine, if_exists="replace", index=False)
    data["branches"].to_sql("branches", engine, if_exists="replace", index=False)
    data["cutoff"].to_sql("cutoff", engine, if_exists="replace", index=False)

    # Store rank tables
    for name, df in ranks.items():
        df.to_sql(name, engine, if_exists="replace", index=False)

    return master


if __name__ == "__main__":
    df = init_db()
    print(f"Master table: {len(df)} rows, {len(df.columns)} columns")
    print("Columns:", list(df.columns))
