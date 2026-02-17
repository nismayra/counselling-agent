"""
Engineering Counselling Decision Web App — Streamlit UI.

Tier-dominant ranking engine with multi-tier selection,
weighted scoring, and interactive filtering.
"""

import streamlit as st
import pandas as pd
from db import init_db, load_csvs, compute_ranks_and_tiers, build_master_table
from ranking import ALL_TIERS, TIER_SCORES
from scoring import apply_tier_filtering_and_scoring

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="TN Engineering Counselling Advisor",
    page_icon=":mortar_board:",
    layout="wide",
)

st.title("TN Engineering Counselling Advisor")
st.caption("Tier-dominant ranking engine for Tamil Nadu engineering college selection")


# ---------------------------------------------------------------------------
# Data loading (cached)
# ---------------------------------------------------------------------------
@st.cache_data
def load_data(year: str) -> pd.DataFrame:
    """Load CSVs, compute ranks/tiers, build master table. Cached per year."""
    data = load_csvs(year)
    ranks = compute_ranks_and_tiers(data["cutoff"])
    master = build_master_table(
        data["cutoff"], data["districts"], data["colleges"], data["branches"], ranks
    )
    return master


# ---------------------------------------------------------------------------
# Year selector (future-ready)
# ---------------------------------------------------------------------------
available_years = ["2020"]
selected_year = st.sidebar.selectbox("Counselling Year", available_years)
master = load_data(selected_year)

# ---------------------------------------------------------------------------
# Sidebar — Tier filters
# ---------------------------------------------------------------------------
st.sidebar.header("Tier Selection")
st.sidebar.markdown("Select which tiers to include per category. Unselected tiers score 0.")

college_tiers = st.sidebar.multiselect(
    "College Tiers",
    ALL_TIERS,
    default=ALL_TIERS,
    help="Filter and score colleges by tier",
)
branch_tiers = st.sidebar.multiselect(
    "Branch Tiers",
    ALL_TIERS,
    default=ALL_TIERS,
    help="Filter and score branches by tier",
)
district_tiers = st.sidebar.multiselect(
    "District Tiers",
    ALL_TIERS,
    default=ALL_TIERS,
    help="Filter and score districts by tier",
)

# ---------------------------------------------------------------------------
# Sidebar — Weightage sliders
# ---------------------------------------------------------------------------
st.sidebar.header("Weightages")
st.sidebar.markdown("Adjust importance (0–100). Weights are normalized internally.")

district_w = st.sidebar.slider("District", 0, 100, 25)
department_w = st.sidebar.slider("Department", 0, 100, 25)
branch_w = st.sidebar.slider("Branch", 0, 100, 25)
college_w = st.sidebar.slider("College", 0, 100, 25)

# Show normalized weights
total_w = district_w + department_w + branch_w + college_w
if total_w > 0:
    st.sidebar.caption(
        f"Normalized: District {district_w/total_w:.0%} | "
        f"Dept {department_w/total_w:.0%} | "
        f"Branch {branch_w/total_w:.0%} | "
        f"College {college_w/total_w:.0%}"
    )

# ---------------------------------------------------------------------------
# Sidebar — Optional row filters (do NOT recompute ranks)
# ---------------------------------------------------------------------------
st.sidebar.header("Filters")

all_districts = sorted(master["District"].dropna().unique())
sel_districts = st.sidebar.multiselect("Filter by District", all_districts)

all_departments = sorted(master["Department"].dropna().unique())
sel_departments = st.sidebar.multiselect("Filter by Department", all_departments)

all_branches = sorted(master["Branch Name"].dropna().unique())
sel_branches = st.sidebar.multiselect("Filter by Branch", all_branches)

all_colleges = sorted(master["College Name"].dropna().unique())
sel_colleges = st.sidebar.multiselect("Filter by College", all_colleges)

# ---------------------------------------------------------------------------
# Apply scoring (on full data — ranks are global)
# ---------------------------------------------------------------------------
scored = apply_tier_filtering_and_scoring(
    master,
    college_tiers=college_tiers or ALL_TIERS,
    branch_tiers=branch_tiers or ALL_TIERS,
    district_tiers=district_tiers or ALL_TIERS,
    district_w=district_w,
    department_w=department_w,
    branch_w=branch_w,
    college_w=college_w,
)

# ---------------------------------------------------------------------------
# Apply row filters (visibility only — no rank recomputation)
# ---------------------------------------------------------------------------
filtered = scored.copy()
if sel_districts:
    filtered = filtered[filtered["District"].isin(sel_districts)]
if sel_departments:
    filtered = filtered[filtered["Department"].isin(sel_departments)]
if sel_branches:
    filtered = filtered[filtered["Branch Name"].isin(sel_branches)]
if sel_colleges:
    filtered = filtered[filtered["College Name"].isin(sel_colleges)]

# ---------------------------------------------------------------------------
# Summary panels — Top Tier entities
# ---------------------------------------------------------------------------
st.subheader("Top Tier Overview")
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("**Top Tier Colleges**")
    top_colleges = (
        scored[scored["college_tier"] == "Top"][["College Name", "college_rank", "college_max_cutoff"]]
        .drop_duplicates(subset=["College Name"])
        .sort_values("college_rank")
        .head(10)
        .rename(columns={
            "College Name": "College",
            "college_rank": "Rank",
            "college_max_cutoff": "Max Cutoff",
        })
    )
    st.dataframe(top_colleges, use_container_width=True, hide_index=True)

with col2:
    st.markdown("**Top Tier Branches**")
    top_branches = (
        scored[scored["branch_tier"] == "Top"][["Branch Name", "branch_rank", "branch_max_cutoff"]]
        .drop_duplicates(subset=["Branch Name"])
        .sort_values("branch_rank")
        .head(10)
        .rename(columns={
            "Branch Name": "Branch",
            "branch_rank": "Rank",
            "branch_max_cutoff": "Max Cutoff",
        })
    )
    st.dataframe(top_branches, use_container_width=True, hide_index=True)

with col3:
    st.markdown("**Top Tier Districts**")
    top_districts = (
        scored[scored["district_tier"] == "Top"][["District", "district_rank", "district_max_cutoff"]]
        .drop_duplicates(subset=["District"])
        .sort_values("district_rank")
        .head(10)
        .rename(columns={
            "District": "District",
            "district_rank": "Rank",
            "district_max_cutoff": "Max Cutoff",
        })
    )
    st.dataframe(top_districts, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Main recommendation table
# ---------------------------------------------------------------------------
st.subheader(f"Recommendations ({len(filtered):,} records)")

# Select and order columns as per spec
display_cols = [
    "choose_order",
    "sum_of_tiers",
    "college_tier",
    "college_tier_score",
    "branch_tier",
    "branch_tier_score",
    "district_tier",
    "district_tier_score",
    "college_rank",
    "branch_rank",
    "district_rank",
    "department_rank",
    "College Name",
    "Branch Name",
    "Department",
    "District",
    "Catogery OC Cutoff",
    "final_score",
]

# Only show columns that exist
display_cols = [c for c in display_cols if c in filtered.columns]

display_df = filtered[display_cols].rename(
    columns={
        "choose_order": "#",
        "sum_of_tiers": "Tier Sum",
        "college_tier": "College Tier",
        "college_tier_score": "C.T Score",
        "branch_tier": "Branch Tier",
        "branch_tier_score": "B.T Score",
        "district_tier": "District Tier",
        "district_tier_score": "D.T Score",
        "college_rank": "College Rank",
        "branch_rank": "Branch Rank",
        "district_rank": "District Rank",
        "department_rank": "Dept Rank",
        "College Name": "College",
        "Branch Name": "Branch",
        "Department": "Department",
        "District": "District",
        "Catogery OC Cutoff": "OC Cutoff",
        "final_score": "Final Score",
    }
)

st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True,
    height=600,
)

# ---------------------------------------------------------------------------
# Weightage info footer
# ---------------------------------------------------------------------------
st.sidebar.markdown("---")
st.sidebar.markdown(
    f"**Applied Weights:** District={district_w}, Dept={department_w}, "
    f"Branch={branch_w}, College={college_w}"
)
st.sidebar.markdown(
    "**Sorting:** Tier Sum DESC > Final Score DESC > OC Cutoff DESC > Ranks ASC"
)
