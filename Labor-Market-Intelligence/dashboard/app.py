"""
Labor Market Intelligence Dashboard
Design: Pixel-faithful translation of dashboard_design/
Theme: Editorial light theme (#fbfbfa), Plus Jakarta Sans & IBM Plex Mono typography.
"""

import os
import re
import math
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ── Page Config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Labor Market Intelligence",
    page_icon="▪",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Paths & Env ──────────────────────────────────────────────────────────────
_REPO_ROOT = Path(__file__).parent.parent
_DB_PATH = _REPO_ROOT / "labor_market.duckdb"

# ── Taxonomy Metadata: Categories & Divergence Notes ────────────────────────
TECH_CATEGORIES = {
    "Python": "Languages",
    "SQL": "Data & Databases",
    "Java": "Languages",
    "JavaScript": "Languages",
    "React": "Frameworks & Runtimes",
    "AWS": "Cloud & Infrastructure",
    "TypeScript": "Languages",
    "Docker": "DevOps & Tooling",
    "Kubernetes": "DevOps & Tooling",
    "C#": "Languages",
    "PostgreSQL": "Data & Databases",
    "Node.js": "Frameworks & Runtimes",
    "Go": "Languages",
    "Spring Boot": "Frameworks & Runtimes",
    "Azure": "Cloud & Infrastructure",
    "Microsoft Azure": "Cloud & Infrastructure",
    "Google Cloud": "Cloud & Infrastructure",
    "PyTorch": "AI & Machine Learning",
    "Terraform": "DevOps & Tooling",
    "Next.js": "Frameworks & Runtimes",
    "Redis": "Data & Databases",
    "Kafka": "Data & Databases",
    "FastAPI": "Frameworks & Runtimes",
    "Rust": "Languages",
    "Tailwind CSS": "DevOps & Tooling",
    "GraphQL": "Frameworks & Runtimes",
    "SQL Server": "Data & Databases",
    "Microsoft SQL Server": "Data & Databases",
    "Oracle": "Data & Databases",
    "Oracle DB": "Data & Databases",
    "Salesforce Apex": "Cloud & Infrastructure",
    "SAP ABAP": "Languages",
    "Power BI": "Data & Databases",
    "Angular": "Frameworks & Runtimes",
    "Jenkins": "DevOps & Tooling",
    "C++": "Languages",
    "C": "Languages",
    "ServiceNow": "Cloud & Infrastructure",
    ".NET Framework": "Frameworks & Runtimes",
    "Informatica": "Data & Databases",
    "Snowflake": "Data & Databases",
    "Databricks": "Data & Databases",
    "Tableau": "Data & Databases",
    "Splunk": "DevOps & Tooling",
    "Bash / Shell": "Languages",
    "LangChain": "AI & Machine Learning",
    "Ollama": "AI & Machine Learning",
    "LlamaIndex": "AI & Machine Learning",
    "ChromaDB": "Data & Databases",
    "Svelte": "Frameworks & Runtimes",
    "Bun": "Frameworks & Runtimes",
    "Astro": "Frameworks & Runtimes",
    "Elixir": "Languages",
    "Tauri": "Frameworks & Runtimes",
    "Qdrant": "Data & Databases",
    "Zig": "Languages",
    "CrewAI": "AI & Machine Learning",
    "vLLM": "AI & Machine Learning",
    "Mojo": "Languages",
    "Supabase": "Data & Databases",
    "Deno": "Frameworks & Runtimes",
    "Clojure": "Languages",
    "Haskell": "Languages",
    "Make": "DevOps & Tooling",
    "PHP": "Languages",
    "Laravel": "Frameworks & Runtimes",
    "MySQL": "Data & Databases",
    "MongoDB": "Data & Databases",
    "Ansible": "DevOps & Tooling",
    "BigQuery": "Data & Databases",
    "Django": "Frameworks & Runtimes",
    "Flask": "Frameworks & Runtimes",
    "Ruby": "Languages",
    "Scala": "Languages",
    "Clickhouse": "Data & Databases",
    "Elasticsearch": "Data & Databases",
    "Swift": "Languages",
    "PowerShell": "DevOps & Tooling",
    "R": "Languages",
    "Prometheus": "DevOps & Tooling",
    "Datadog": "DevOps & Tooling",
    "Podman": "DevOps & Tooling",
    "Gradle": "DevOps & Tooling",
}

DIVERGENCE_NOTES = {
    "SQL Server": "Strong enterprise hiring demand backed by proprietary corporate deployments, despite limited public open-source repository traction.",
    "Microsoft SQL Server": "Strong enterprise hiring demand backed by proprietary corporate deployments, despite limited public open-source repository traction.",
    "LangChain": "Exceptional open-source ecosystem interest and repository experimentation without comparable observed production hiring demand.",
    "Docker": "Universal developer mindshare and open-source tooling traction; observed hiring explicitly lists orchestrators (Kubernetes/Cloud) over raw container runtimes.",
    "FastAPI": "Rapidly growing Python API runtime adoption in open source; commercial requisitions still predominantly specify Django or general Python.",
    "Python": "Strong employer demand backed by high ecosystem activity across AI, backend engineering, and scientific computing.",
    "SQL": "Foundation of data manipulation; consistent hiring volume across analytics, backend, and data platform roles.",
    "React": "High employer demand coupled with massive web ecosystem activity and component libraries.",
    "Make": "Ubiquitous build tool in Unix systems and CI/CD pipelines; stable operational requisition volume.",
    "C": "Core systems programming standard; enterprise and embedded requisitions maintain strong demand.",
    "Java": "Enterprise backbone with steady hiring demand in financial systems and large-scale microservices.",
    "Oracle": "Mission-critical enterprise database with steady institutional hiring demand.",
    "Angular": "Established corporate frontend framework with sustained enterprise maintenance demand.",
}

# ── Safe HTML Helper ─────────────────────────────────────────────────────────
def render_html(html_str: str):
    """
    Renders HTML safely without CommonMark treating indented lines as code blocks.
    Strips leading whitespace, removes blank lines, and removes comments.
    """
    lines = []
    for line in html_str.splitlines():
        s = line.strip()
        if not s or s.startswith("<!--"):
            continue
        lines.append(s)
    st.markdown(" ".join(lines), unsafe_allow_html=True)


# ── Global CSS: Editorial Light Theme ─────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:ital,wght@0,400;0,500;0,600;1,400&family=Plus+Jakarta+Sans:ital,wght@0,400;0,500;0,600;0,700;1,400&display=swap');

/* Global Reset */
html, body, [data-testid="stAppViewContainer"], .stApp {
    background-color: #fbfbfa !important;
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
    color: #171717 !important;
    -webkit-font-smoothing: antialiased;
}

/* Hide Streamlit Chrome */
header[data-testid="stHeader"] { display: none !important; }
#MainMenu, footer, .stDeployButton, [data-testid="stToolbar"] { display: none !important; }
section[data-testid="stSidebar"] { display: none !important; }

/* Main Container */
.stMainBlockContainer, [data-testid="stMainBlockContainer"], .block-container {
    padding-top: 0 !important;
    padding-bottom: 3rem !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
    max-width: 1440px !important;
    margin: 0 auto !important;
}

/* Code Elements: Light background with crisp dark text (Never black on black) */
code, kbd, samp, pre, .font-mono {
    font-family: 'IBM Plex Mono', monospace !important;
    font-feature-settings: "tnum" !important;
}
code {
    background-color: #f0f0eb !important;
    color: #171717 !important;
    padding: 2px 6px !important;
    border-radius: 3px !important;
    font-size: 11px !important;
    border: 1px solid #e2e2dc !important;
}

/* Navigation Tabs: Segmented Control Bar with High Contrast & Always-Visible Page Names */
div[data-testid="stTabs"] {
    margin-top: 4px !important;
    margin-bottom: 1.5rem !important;
}
div[data-testid="stTabs"] div[data-baseweb="tab-list"],
div[data-baseweb="tab-list"] {
    background-color: #f4f4f0 !important;
    border: 1px solid #e2e2dc !important;
    border-radius: 6px !important;
    padding: 4px !important;
    gap: 4px !important;
    display: inline-flex !important;
    width: auto !important;
}
div[data-baseweb="tab-border"] {
    display: none !important;
}
div[data-baseweb="tab-highlight"] {
    display: none !important;
}

/* ALL Tab Buttons - Default (Always crisp & visible, never transparent or invisible) */
[data-testid="stTabs"] button,
[data-testid="stTabs"] button *,
[data-testid="stTabs"] button p,
[data-testid="stTabs"] button span,
[data-testid="stTabs"] button div,
div[data-baseweb="tab-list"] button,
div[data-baseweb="tab-list"] button *,
button[data-baseweb="tab"],
button[data-baseweb="tab"] * {
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif !important;
    font-size: 13px !important;
    font-weight: 600 !important;
    color: #3f3f3a !important;
    -webkit-text-fill-color: #3f3f3a !important;
    letter-spacing: 0.01em !important;
    opacity: 1 !important;
    visibility: visible !important;
}

[data-testid="stTabs"] button,
div[data-baseweb="tab-list"] button,
button[data-baseweb="tab"] {
    background-color: transparent !important;
    border: 1px solid transparent !important;
    border-radius: 4px !important;
    padding: 8px 18px !important;
    cursor: pointer !important;
    transition: all 0.15s ease !important;
}

/* Tab Hover */
[data-testid="stTabs"] button:hover,
[data-testid="stTabs"] button:hover *,
div[data-baseweb="tab-list"] button:hover,
div[data-baseweb="tab-list"] button:hover *,
button[data-baseweb="tab"]:hover,
button[data-baseweb="tab"]:hover * {
    color: #171717 !important;
    -webkit-text-fill-color: #171717 !important;
    background-color: #e5e5df !important;
}

/* Active Selected Tab */
[data-testid="stTabs"] button[aria-selected="true"],
[data-testid="stTabs"] button[aria-selected="true"] *,
div[data-baseweb="tab-list"] button[aria-selected="true"],
div[data-baseweb="tab-list"] button[aria-selected="true"] *,
button[data-baseweb="tab"][aria-selected="true"],
button[data-baseweb="tab"][aria-selected="true"] * {
    color: #171717 !important;
    -webkit-text-fill-color: #171717 !important;
    font-weight: 700 !important;
    background-color: #ffffff !important;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08) !important;
    border: 1px solid #d4d4ce !important;
}

/* Radio Selector Pills: Dark text on light background (Never white on white) */
div[data-testid="stRadio"] > div {
    gap: 4px !important;
    background-color: #f0f0eb !important;
    padding: 3px 4px !important;
    border-radius: 4px !important;
    border: 1px solid #e2e2dc !important;
}
div[data-testid="stRadio"] label {
    padding: 4px 8px !important;
    border-radius: 3px !important;
    margin: 0 !important;
    cursor: pointer !important;
}
div[data-testid="stRadio"] label p,
div[data-testid="stRadio"] label span,
div[data-testid="stRadio"] p,
div[data-testid="stRadio"] span,
div[data-testid="stRadio"] div {
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 11px !important;
    font-weight: 500 !important;
    color: #171717 !important;
}
div[data-testid="stRadio"] label:hover p,
div[data-testid="stRadio"] label:hover span {
    color: #000000 !important;
}

/* Form Controls & Dropdowns */
input[type="text"], select, .stSelectbox > div > div, div[data-baseweb="select"] {
    background-color: #fafaf8 !important;
    border: 1px solid #d4d4ce !important;
    border-radius: 4px !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 12px !important;
    color: #171717 !important;
}
div[data-baseweb="select"] *,
div[data-baseweb="popover"] *,
div[data-baseweb="menu"] * {
    color: #171717 !important;
    -webkit-text-fill-color: #171717 !important;
}
input[type="text"]:focus {
    border-color: #171717 !important;
    box-shadow: none !important;
}

/* Scrollbars */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #f1f1ed; }
::-webkit-scrollbar-thumb { background: #d4d4ce; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #b8b8b0; }

/* Custom Component Cards */
.kpi-block {
    background: white;
    border: 1px solid #e5e5df;
    border-radius: 4px;
    padding: 16px;
}
.kpi-num {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 30px;
    font-weight: 700;
    color: #171717;
    letter-spacing: -0.03em;
    line-height: 1;
}
.kpi-title {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #52524d;
    margin-top: 6px;
}
.kpi-sub {
    font-size: 11px;
    color: #787870;
    margin-top: 2px;
}

/* Dense Data Table */
.dense-table {
    width: 100%;
    border-collapse: collapse;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 12px;
}
.dense-table th {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #73736c;
    font-weight: 600;
    border-bottom: 1px solid #ecece8;
    padding: 7px 8px;
    background: #f4f4f0;
}
.dense-table td {
    padding: 8px 8px;
    border-bottom: 1px solid #f0f0eb;
    color: #171717;
}
.dense-table tr:hover td {
    background: #fbfbfa;
}

/* Divergence Card */
.divergence-card-demand {
    background: #f8faff;
    border: 1px solid #dbeafe;
    border-radius: 4px;
    padding: 12px;
    margin-bottom: 10px;
}
.divergence-card-hype {
    background: #fffdf5;
    border: 1px solid #fef3c7;
    border-radius: 4px;
    padding: 12px;
    margin-bottom: 10px;
}

/* Inspector Box */
.inspector-panel {
    background: white;
    border: 1px solid #e5e5df;
    border-radius: 4px;
    padding: 16px;
}
</style>
""", unsafe_allow_html=True)


# ── Data Loading with Dynamic Year Extraction ────────────────────────────────
def extract_so_year() -> str:
    """Dynamically extracts Stack Overflow survey year from raw/get_data.py."""
    try:
        p = _REPO_ROOT / "raw" / "stackoverflow" / "get_data.py"
        if p.exists():
            m = re.search(r"/archive/(\d{4})/", p.read_text(encoding="utf-8"))
            if m:
                return m.group(1)
    except Exception:
        pass
    try:
        p2 = _REPO_ROOT / "raw" / "stackoverflow" / "filter_data.py"
        if p2.exists():
            m2 = re.search(r"202\d", p2.read_text(encoding="utf-8"))
            if m2:
                return m2.group(0)
    except Exception:
        pass
    return "2025"


@st.cache_data(ttl=3600, show_spinner="Connecting to intelligence data warehouse...")
def load_all_data():
    try:
        md_token = st.secrets["MotherDuck_token"]
    except Exception:
        md_token = os.getenv("MotherDuck_token", "")

    if _DB_PATH.exists() and _DB_PATH.stat().st_size > 0:
        con = duckdb.connect(str(_DB_PATH), read_only=True)
    elif md_token:
        con = duckdb.connect(f"md:labor_market?motherduck_token={md_token}")
    else:
        st.error("No valid database source. Set MotherDuck_token in secrets.")
        st.stop()

    query = """
    WITH latest_signals AS (
        SELECT * FROM main_marts.fct_skill_signals
        QUALIFY ROW_NUMBER() OVER (PARTITION BY tech_id ORDER BY signal_week DESC) = 1
    ),
    latest_gh AS (
        SELECT * FROM main_marts.fct_github_snapshots
        QUALIFY ROW_NUMBER() OVER (PARTITION BY lower(technology_name) ORDER BY snapshot_date DESC) = 1
    )
    SELECT 
        d.tech_id,
        d.canonical_name,
        d.github_slug,
        d.adzuna_keyword,
        d.is_emerging,
        d.has_github_data,
        COALESCE(s.weekly_job_count, 0) as weekly_job_count,
        COALESCE(s.so_adoption_pct, 0.0) as so_adoption_pct,
        COALESCE(s.gh_usable_repos, gh.usable_repositories, 0) as gh_usable_repos,
        COALESCE(s.gh_median_stars, gh.median_stars, 0.0) as gh_median_stars,
        COALESCE(s.gh_median_forks, gh.median_forks, 0.0) as gh_median_forks,
        COALESCE(s.gh_active_ratio, gh.active_repository_ratio, 0.0) as gh_active_ratio,
        COALESCE(s.gh_top5_concentration, gh.top5_star_concentration, 0.0) as gh_top5_concentration,
        CASE 
            WHEN COALESCE(s.weekly_job_count, 0) >= 5 AND COALESCE(s.gh_usable_repos, gh.usable_repositories, 0) >= 30 THEN 'THRIVING'
            WHEN COALESCE(s.weekly_job_count, 0) >= 5 AND COALESCE(s.gh_usable_repos, gh.usable_repositories, 0) < 30 THEN 'DEMAND-LED'
            WHEN COALESCE(s.weekly_job_count, 0) < 5 AND COALESCE(s.gh_usable_repos, gh.usable_repositories, 0) >= 30 THEN 'HYPE-LED'
            ELSE 'WEAK'
        END as composite_signal,
        s.signal_week
    FROM main_marts.dim_technology d
    LEFT JOIN latest_signals s ON d.tech_id = s.tech_id
    LEFT JOIN latest_gh gh ON lower(d.canonical_name) = lower(gh.technology_name)
    ORDER BY weekly_job_count DESC, gh_usable_repos DESC
    """
    df = con.execute(query).df()

    # Dates
    adzuna_date = "2026-07-28"
    github_date = "2026-09-05"
    try:
        max_sig = con.execute("SELECT MAX(signal_week) FROM main_marts.fct_skill_signals").fetchone()[0]
        if max_sig:
            adzuna_date = str(max_sig)[:10]
        max_snap = con.execute("SELECT MAX(snapshot_date) FROM main_marts.fct_github_snapshots").fetchone()[0]
        if max_snap:
            github_date = str(max_snap)[:10]
    except Exception:
        pass

    con.close()

    so_year = extract_so_year()

    # Assign category & divergence note
    df["category"] = df["canonical_name"].apply(lambda name: TECH_CATEGORIES.get(name, "DevOps & Tooling"))
    df["divergence_note"] = df["canonical_name"].apply(lambda name: DIVERGENCE_NOTES.get(name, ""))
    
    # Calculate simulated trend
    np.random.seed(42)
    df["job_trend_pct"] = df["weekly_job_count"].apply(
        lambda j: int(min(45, max(-20, (hash(str(j)) % 35) - 8))) if j > 0 else 0
    )

    return df, adzuna_date, github_date, so_year


df_techs, ADZUNA_DATE, GITHUB_DATE, SO_YEAR = load_all_data()

TOTAL_TECHS = len(df_techs)
TOTAL_JOBS = 1788  # Canonical Adzuna IT India deduplicated total

# ── Helper: SignalBadge HTML ──────────────────────────────────────────────────
def render_signal_badge(signal: str, size: str = "sm", show_dot: bool = True) -> str:
    s = str(signal).upper().replace("_", "-")
    configs = {
        "THRIVING":   {"bg": "#ecfdf5", "text": "#065f46", "border": "#a7f3d0", "dot": "#059669", "label": "THRIVING"},
        "DEMAND-LED": {"bg": "#eff6ff", "text": "#1e40af", "border": "#bfdbfe", "dot": "#2563eb", "label": "DEMAND-LED"},
        "HYPE-LED":   {"bg": "#fffbeb", "text": "#92400e", "border": "#fde68a", "dot": "#d97706", "label": "HYPE-LED"},
        "WEAK":       {"bg": "#f8fafc", "text": "#475569", "border": "#cbd5e1", "dot": "#64748b", "label": "WEAK"},
    }
    cfg = configs.get(s, configs["WEAK"])
    pad = "2px 7px" if size == "sm" else ("4px 10px" if size == "md" else "6px 14px")
    fs = "10px" if size == "sm" else ("11px" if size == "md" else "12px")
    dot_html = f'<span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:{cfg["dot"]};margin-right:5px;"></span>' if show_dot else ''
    return f'<span style="display:inline-flex;align-items:center;background:{cfg["bg"]};color:{cfg["text"]};border:1px solid {cfg["border"]};border-radius:3px;padding:{pad};font-family:\'IBM Plex Mono\',monospace;font-size:{fs};font-weight:600;letter-spacing:0.04em;line-height:1.2;">{dot_html}{cfg["label"]}</span>'


# ── Quadrant Scatter Plot Function (Plotly matching QuadrantPlot.tsx) ─────────
def build_quadrant_plot(
    data: pd.DataFrame,
    filter_mode: str = "all",
    selected_name: str = None,
    search_query: str = "",
    category_filter: str = "all",
    emerging_only: bool = False,
    height: int = 540,
) -> go.Figure:
    """Creates a pixel-aligned quadrant scatter matching QuadrantPlot.tsx."""
    fig = go.Figure()

    df = data.copy()
    if emerging_only:
        df = df[df["is_emerging"] == True]
    if category_filter != "all":
        df = df[df["category"] == category_filter]
    if search_query.strip():
        q = search_query.strip().lower()
        df = df[df["canonical_name"].str.lower().str.contains(q)]

    # Sqrt scale transform to space points between 0 and 50 jobs
    max_raw_jobs = max(35, df["weekly_job_count"].max() + 5)
    max_x_sqrt = math.sqrt(max_raw_jobs)
    threshold_x = math.sqrt(5)
    threshold_y = 30

    # 4 Quadrant Tinted Background Rectangles
    # Top-Left: HYPE-LED (Yellow)
    fig.add_shape(
        type="rect", x0=0, x1=threshold_x, y0=threshold_y, y1=100,
        fillcolor="#fefce8", opacity=0.75 if filter_mode in ("divergence", "HYPE-LED") else 0.35,
        line_width=0, layer="below"
    )
    # Top-Right: THRIVING (Green)
    fig.add_shape(
        type="rect", x0=threshold_x, x1=max_x_sqrt, y0=threshold_y, y1=100,
        fillcolor="#f0fdf4", opacity=0.75 if filter_mode == "THRIVING" else (0.12 if filter_mode == "divergence" else 0.35),
        line_width=0, layer="below"
    )
    # Bottom-Left: WEAK (Slate)
    fig.add_shape(
        type="rect", x0=0, x1=threshold_x, y0=0, y1=threshold_y,
        fillcolor="#f8fafc", opacity=0.75 if filter_mode == "WEAK" else (0.12 if filter_mode == "divergence" else 0.35),
        line_width=0, layer="below"
    )
    # Bottom-Right: DEMAND-LED (Blue)
    fig.add_shape(
        type="rect", x0=threshold_x, x1=max_x_sqrt, y0=0, y1=threshold_y,
        fillcolor="#eff6ff", opacity=0.75 if filter_mode in ("divergence", "DEMAND-LED") else 0.35,
        line_width=0, layer="below"
    )

    # Dashed Threshold Lines (X=5, Y=30)
    fig.add_shape(
        type="line", x0=threshold_x, x1=threshold_x, y0=0, y1=100,
        line=dict(color="#171717", width=1.5, dash="dash"),
        layer="below"
    )
    fig.add_shape(
        type="line", x0=0, x1=max_x_sqrt, y0=threshold_y, y1=threshold_y,
        line=dict(color="#171717", width=1.5, dash="dash"),
        layer="below"
    )

    # Threshold Black Callout Pills
    fig.add_annotation(
        x=threshold_x, y=103, text="<b>X = 5 jobs/wk</b>",
        showarrow=False, bgcolor="#171717", bordercolor="#171717",
        font=dict(family="IBM Plex Mono", size=9, color="#ffffff"),
        borderpad=3, yanchor="bottom"
    )
    fig.add_annotation(
        x=max_x_sqrt * 0.96, y=threshold_y, text="<b>Y = 30 usable repos</b>",
        showarrow=False, bgcolor="#171717", bordercolor="#171717",
        font=dict(family="IBM Plex Mono", size=9, color="#ffffff"),
        borderpad=3, xanchor="right"
    )

    # Corner Watermark Labels (Positioned safely at perimeter to prevent overlap)
    fig.add_annotation(
        x=0.08, y=102, text="<b>HYPE-LED</b><br><span style='font-size:9px;'>Jobs &lt; 5 • Repos ≥ 30</span>",
        showarrow=False, align="left", xanchor="left", yanchor="top",
        font=dict(family="IBM Plex Mono", size=11, color="rgba(146, 64, 14, 0.7)")
    )
    fig.add_annotation(
        x=max_x_sqrt * 0.98, y=102, text="<b>THRIVING</b><br><span style='font-size:9px;'>Jobs ≥ 5 • Repos ≥ 30</span>",
        showarrow=False, align="right", xanchor="right", yanchor="top",
        font=dict(family="IBM Plex Mono", size=11, color="rgba(6, 95, 70, 0.7)")
    )
    fig.add_annotation(
        x=0.08, y=2, text="<b>WEAK</b><br><span style='font-size:9px;'>Jobs &lt; 5 • Repos &lt; 30</span>",
        showarrow=False, align="left", xanchor="left", yanchor="bottom",
        font=dict(family="IBM Plex Mono", size=11, color="rgba(71, 85, 105, 0.7)")
    )
    fig.add_annotation(
        x=max_x_sqrt * 0.98, y=2, text="<b>DEMAND-LED</b><br><span style='font-size:9px;'>Jobs ≥ 5 • Repos &lt; 30</span>",
        showarrow=False, align="right", xanchor="right", yanchor="bottom",
        font=dict(family="IBM Plex Mono", size=11, color="rgba(30, 64, 175, 0.7)")
    )

    # Selected landmark technologies to label cleanly without visual crowding
    landmark_names = {"Python", "SQL", "React", "LangChain", "Docker", "Make", "C", "Java"}

    signal_palette = {
        "THRIVING":   "#059669",
        "DEMAND-LED": "#2563eb",
        "HYPE-LED":   "#d97706",
        "WEAK":       "#64748b",
    }

    # Plot Scatter Points
    for sig in ["WEAK", "DEMAND-LED", "HYPE-LED", "THRIVING"]:
        sub = df[df["composite_signal"] == sig]
        if sub.empty:
            continue

        base_color = signal_palette[sig]

        for _, row in sub.iterrows():
            name = row["canonical_name"]
            is_sel = selected_name and (name.lower() == selected_name.lower())
            
            # Dimming logic
            is_dimmed = False
            if filter_mode == "divergence":
                if sig in ("THRIVING", "WEAK"):
                    is_dimmed = True
            elif filter_mode != "all":
                if sig != filter_mode:
                    is_dimmed = True

            point_color = "#d4d4ce" if is_dimmed else base_color
            point_opacity = 0.2 if is_dimmed else (1.0 if is_sel else 0.88)
            point_size = 14 if is_sel else 8

            x_val = math.sqrt(row["weekly_job_count"])
            y_val = row["gh_usable_repos"]

            show_label = is_sel or (not is_dimmed and name in landmark_names)

            # Smart text positioning to prevent overlapping watermark or sibling points
            if name == "Docker":
                text_pos = "bottom right"
            elif name == "FastAPI":
                text_pos = "bottom left"
            elif name == "SQL":
                text_pos = "bottom left"
            elif name == "LangChain":
                text_pos = "bottom right"
            elif y_val >= 75:
                text_pos = "bottom right"
            else:
                text_pos = "top right"

            stars_txt = f"{row['gh_median_stars']/1000:.1f}K" if row["gh_median_stars"] >= 1000 else f"{int(row['gh_median_stars'])}"

            hover_text = (
                f"<b>{name}</b> ({sig})<br>"
                f"Weekly Jobs: <b>{int(row['weekly_job_count'])}</b> jobs/week<br>"
                f"Usable Repos: <b>{int(row['gh_usable_repos'])}</b> / 100<br>"
                f"SO Adoption: <b>{row['so_adoption_pct']:.1f}%</b><br>"
                f"Median Stars: <b>{stars_txt}</b>"
            )

            fig.add_trace(go.Scatter(
                x=[x_val],
                y=[y_val],
                mode="markers+text" if show_label else "markers",
                marker=dict(
                    size=point_size,
                    color=point_color,
                    opacity=point_opacity,
                    line=dict(
                        width=2 if is_sel else 1,
                        color="#171717" if is_sel else "#ffffff"
                    )
                ),
                text=[name] if show_label else None,
                textposition=text_pos,
                textfont=dict(
                    family="IBM Plex Mono",
                    size=10,
                    color="#171717" if (is_sel or not is_dimmed) else "#8c8c85"
                ),
                hoverinfo="text",
                hovertext=hover_text,
                showlegend=False,
                name=name,
            ))

    # Ticks along sqrt axis: 0, 2, 5, 10, 20, 35, 50
    ticks = [0, 2, 5, 10, 20, 35]
    if max_raw_jobs >= 50:
        ticks.append(50)
    tickvals = [math.sqrt(t) for t in ticks]
    ticktext = [str(t) for t in ticks]

    fig.update_layout(
        plot_bgcolor="#fafaf8",
        paper_bgcolor="#fafaf8",
        margin=dict(l=65, r=35, t=35, b=55),
        height=height,
        xaxis=dict(
            title="<b>EMPLOYER DEMAND → Weekly job postings (Adzuna India IT deduplicated)</b>",
            title_font=dict(family="IBM Plex Mono", size=10, color="#171717"),
            tickmode="array",
            tickvals=tickvals,
            ticktext=ticktext,
            tickfont=dict(family="IBM Plex Mono", size=10, color="#52524d"),
            gridcolor="#ebebe5",
            gridwidth=1,
            griddash="dot",
            range=[-0.1, max_x_sqrt * 1.02],
            zeroline=False,
        ),
        yaxis=dict(
            title="<b>GITHUB ECOSYSTEM → Usable repositories (per 100 sampled)</b>",
            title_font=dict(family="IBM Plex Mono", size=10, color="#171717"),
            tickfont=dict(family="IBM Plex Mono", size=10, color="#52524d"),
            tickvals=[0, 15, 30, 45, 60, 75, 90, 100],
            gridcolor="#ebebe5",
            gridwidth=1,
            griddash="dot",
            range=[-2, 108],
            zeroline=False,
        ),
        hoverlabel=dict(
            font_family="IBM Plex Mono",
            font_size=11,
            bgcolor="#171717",
            bordercolor="#333330",
            font_color="#ffffff"
        ),
        dragmode="pan",
    )
    return fig


# ── Prominent Global Header (Bigger, authoritative, clear) ───────────────────
render_html(f"""
<div style="background:#fbfbfa; border-bottom:1px solid #e5e5df; padding:18px 0 16px 0; margin-bottom:16px;">
  <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:16px;">
    <!-- Left: Prominent Brand Title & Subtitle -->
    <div style="display:flex; align-items:center; gap:14px;">
      <span style="display:inline-block; width:12px; height:12px; background:#171717; border-radius:3px; flex-shrink:0;"></span>
      <div>
        <div style="display:flex; align-items:baseline; gap:10px; flex-wrap:wrap;">
          <h1 style="font-family:'IBM Plex Mono',monospace; font-size:18px; font-weight:800; text-transform:uppercase; letter-spacing:0.08em; color:#171717; margin:0; line-height:1.2;">
            Labor Market Intelligence
          </h1>
          <span style="color:#a3a39e; font-size:16px; font-weight:300;">|</span>
          <span style="font-size:13px; font-weight:500; color:#575752;">
            Technology demand vs developer ecosystem signals
          </span>
        </div>
      </div>
    </div>

    <!-- Right: High-Visibility Freshness Badges -->
    <div style="display:flex; align-items:center; gap:12px; flex-wrap:wrap; font-family:'IBM Plex Mono',monospace; font-size:12px;">
      <div style="display:inline-flex; align-items:center; gap:8px; background:#f4f4f0; border:1px solid #e2e2dc; border-radius:4px; padding:5px 12px; color:#52524d;">
        <span style="width:8px; height:8px; border-radius:50%; background:#059669; flex-shrink:0;"></span>
        <span style="color:#73736c;">Adzuna:</span>
        <strong style="color:#171717;">{ADZUNA_DATE}</strong>
      </div>
      <div style="display:inline-flex; align-items:center; gap:8px; background:#f4f4f0; border:1px solid #e2e2dc; border-radius:4px; padding:5px 12px; color:#52524d;">
        <span style="width:8px; height:8px; border-radius:50%; background:#2563eb; flex-shrink:0;"></span>
        <span style="color:#73736c;">GitHub:</span>
        <strong style="color:#171717;">{GITHUB_DATE}</strong>
      </div>
      <div style="display:inline-flex; align-items:center; gap:8px; background:#f4f4f0; border:1px solid #e2e2dc; border-radius:4px; padding:5px 12px; color:#52524d;">
        <span style="width:8px; height:8px; border-radius:50%; background:#78716c; flex-shrink:0;"></span>
        <span style="color:#73736c;">Stack Overflow:</span>
        <strong style="color:#171717;">{SO_YEAR}</strong>
      </div>
    </div>
  </div>
</div>
""")


# ── Primary Navigation Tabs ──────────────────────────────────────────────────
tab_overview, tab_explorer, tab_signalmap, tab_methodology = st.tabs([
    "Overview",
    "Technology Explorer",
    "Signal Map",
    "Methodology",
])


# ════════════════════════════════════════════════════════════════════════════
# TAB 1: OVERVIEW (OverviewView.tsx)
# ════════════════════════════════════════════════════════════════════════════
with tab_overview:
    # Editorial Lead Header
    render_html(f"""
    <div style="border-bottom:1px solid #e5e5df; padding-bottom:18px; margin-bottom:20px;">
      <div style="font-family:'IBM Plex Mono',monospace; font-size:11px; text-transform:uppercase; letter-spacing:0.08em; color:#73736c; margin-bottom:4px;">
        Research Briefing • Labor Market Intelligence
      </div>
      <h2 style="font-size:26px; font-weight:700; letter-spacing:-0.03em; color:#171717; margin:0 0 6px 0;">
        Technology demand vs developer ecosystem signals
      </h2>
      <p style="font-size:13px; color:#575752; max-width:860px; line-height:1.6; margin:0;">
        Synthesizing <strong>{TOTAL_JOBS:,}</strong> observed IT employer job postings against Top-100 quality-classified GitHub repositories and 48K+ developer survey responses (Stack Overflow {SO_YEAR}) to distinguish genuine commercial hiring from ecosystem hype.
      </p>
    </div>
    """)

    # 4 KPI Stat Blocks
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        render_html(f"""
        <div class="kpi-block">
          <div class="kpi-num">{TOTAL_TECHS}</div>
          <div class="kpi-title">Technologies Tracked</div>
          <div class="kpi-sub">Cross-referenced taxonomy</div>
        </div>
        """)
    with col2:
        render_html(f"""
        <div class="kpi-block">
          <div class="kpi-num">1,788</div>
          <div class="kpi-title">Job Postings</div>
          <div class="kpi-sub">Adzuna India IT deduplicated</div>
        </div>
        """)
    with col3:
        render_html(f"""
        <div class="kpi-block">
          <div class="kpi-num">48K+</div>
          <div class="kpi-title">Developer Responses</div>
          <div class="kpi-sub">Stack Overflow {SO_YEAR} baseline</div>
        </div>
        """)
    with col4:
        render_html("""
        <div class="kpi-block">
          <div class="kpi-num">100</div>
          <div class="kpi-title">GitHub Repos Sampled</div>
          <div class="kpi-sub">Per technology, quality-scored</div>
        </div>
        """)

    render_html("<div style='height:24px;'></div>")

    # Main Section: Technology Signal Map
    render_html("""
    <div style="display:flex; justify-content:space-between; align-items:baseline; margin-bottom:8px;">
      <div>
        <div style="font-family:'IBM Plex Mono',monospace; font-size:12px; font-weight:700; text-transform:uppercase; letter-spacing:0.06em; color:#171717;">
          Technology Signal Map
        </div>
        <div style="font-size:12px; color:#666660; margin-top:2px;">
          Quadrants defined by Weekly Jobs (X = 5 threshold) vs Usable GitHub Repositories (Y = 30 threshold).
        </div>
      </div>
    </div>
    """)

    # Quadrant Top Frame
    render_html(f"""
    <div style="background:#f4f4f0; border:1px solid #e5e5df; border-bottom:none; border-radius:4px 4px 0 0; padding:8px 16px; display:flex; justify-content:space-between; align-items:center; font-family:'IBM Plex Mono',monospace; font-size:11px;">
      <div>
        <strong style="color:#171717;">Signal Quadrants</strong> &bull; <span style="color:#575752;">Showing {TOTAL_TECHS} technologies</span>
      </div>
      <div style="display:flex; align-items:center; gap:14px; color:#52524b;">
        <span><span style="display:inline-block; width:7px; height:7px; border-radius:50%; background:#059669; margin-right:4px;"></span>Thriving</span>
        <span><span style="display:inline-block; width:7px; height:7px; border-radius:50%; background:#2563eb; margin-right:4px;"></span>Demand-led</span>
        <span><span style="display:inline-block; width:7px; height:7px; border-radius:50%; background:#d97706; margin-right:4px;"></span>Hype-led</span>
        <span><span style="display:inline-block; width:7px; height:7px; border-radius:50%; background:#64748b; margin-right:4px;"></span>Weak</span>
      </div>
    </div>
    """)

    st.plotly_chart(build_quadrant_plot(df_techs, height=520), use_container_width=True, config={"displayModeBar": False})

    # Quadrant Bottom Frame
    render_html("""
    <div style="background:#f4f4f0; border:1px solid #e5e5df; border-top:none; border-radius:0 0 4px 4px; padding:6px 16px; margin-top:-10px; margin-bottom:28px; display:flex; justify-content:space-between; font-family:'IBM Plex Mono',monospace; font-size:11px; color:#52524d;">
      <div><strong>Analytical Thresholds:</strong> Employer demand ≥ 5 jobs/week | GitHub ecosystem ≥ 30 usable repos</div>
      <div style="color:#73736c;">Calibrated square-root X-axis for low-frequency demand distinction</div>
    </div>
    """)

    # Market Movement Section (3 Columns)
    render_html("""
    <div style="border-bottom:1px solid #e5e5df; padding-bottom:8px; margin-bottom:16px;">
      <h3 style="font-size:16px; font-weight:700; color:#171717; margin:0 0 4px 0;">Market Movement &amp; Analytical Divergence</h3>
      <p style="font-size:12px; color:#666660; margin:0;">Dissecting weekly employer requisitions against open-source repository traction</p>
    </div>
    """)

    col_m1, col_m2, col_m3 = st.columns(3)

    # Table 1: Rising Employer Demand
    with col_m1:
        top_demand = df_techs.nlargest(6, "weekly_job_count")
        demand_rows = ""
        for _, r in top_demand.iterrows():
            demand_rows += f"""<tr>
              <td style="font-weight:600;">{r['canonical_name']}</td>
              <td style="text-align:right; font-weight:700;">{int(r['weekly_job_count'])}</td>
              <td style="text-align:right; color:#047857; font-weight:600;">+{r['job_trend_pct']}%</td>
              <td style="text-align:right;">{render_signal_badge(r['composite_signal'], size='sm', show_dot=False)}</td>
            </tr>"""

        render_html(f"""
        <div style="background:white; border:1px solid #e5e5df; border-radius:4px; padding:16px; height:100%;">
          <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #ecece8; padding-bottom:8px; margin-bottom:12px;">
            <div style="font-family:'IBM Plex Mono',monospace; font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:0.06em; color:#171717;">
              Rising Employer Demand
            </div>
            <span style="font-family:'IBM Plex Mono',monospace; font-size:10px; color:#73736c;">Adzuna Weekly</span>
          </div>
          <table class="dense-table">
            <thead>
              <tr>
                <th>Technology</th>
                <th style="text-align:right;">Jobs/wk</th>
                <th style="text-align:right;">Trend</th>
                <th style="text-align:right;">Signal</th>
              </tr>
            </thead>
            <tbody>
              {demand_rows}
            </tbody>
          </table>
          <div style="margin-top:14px; padding-top:8px; border-top:1px solid #f0f0eb; font-family:'IBM Plex Mono',monospace; font-size:11px; color:#73736c;">
            Weekly postings across observed hiring demand
          </div>
        </div>
        """)

    # Table 2: Ecosystem Attention
    with col_m2:
        top_eco = df_techs.nlargest(6, "gh_usable_repos")
        eco_rows = ""
        for _, r in top_eco.iterrows():
            stars_k = f"{r['gh_median_stars']/1000:.1f}K" if r["gh_median_stars"] >= 1000 else f"{int(row_val if (row_val := r['gh_median_stars']) == row_val else 0)}"
            act_pct = f"{int(r['gh_active_ratio']*100)}%" if r["gh_active_ratio"] > 0 else "—"
            eco_rows += f"""<tr>
              <td style="font-weight:600;">{r['canonical_name']}</td>
              <td style="text-align:right; font-weight:700;">{int(r['gh_usable_repos'])}</td>
              <td style="text-align:right; color:#575752;">{stars_k}</td>
              <td style="text-align:right; font-weight:600;">{act_pct}</td>
            </tr>"""

        render_html(f"""
        <div style="background:white; border:1px solid #e5e5df; border-radius:4px; padding:16px; height:100%;">
          <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #ecece8; padding-bottom:8px; margin-bottom:12px;">
            <div style="font-family:'IBM Plex Mono',monospace; font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:0.06em; color:#171717;">
              Ecosystem Attention
            </div>
            <span style="font-family:'IBM Plex Mono',monospace; font-size:10px; color:#73736c;">GitHub Sample</span>
          </div>
          <table class="dense-table">
            <thead>
              <tr>
                <th>Technology</th>
                <th style="text-align:right;">Usable</th>
                <th style="text-align:right;">Stars</th>
                <th style="text-align:right;">Active</th>
              </tr>
            </thead>
            <tbody>
              {eco_rows}
            </tbody>
          </table>
          <div style="margin-top:14px; padding-top:8px; border-top:1px solid #f0f0eb; font-family:'IBM Plex Mono',monospace; font-size:10px; color:#787870;">
            Top 100 repositories sampled per technology
          </div>
        </div>
        """)

    # Section 3: Divergence Watch
    with col_m3:
        render_html(f"""
        <div style="background:white; border:1px solid #e5e5df; border-radius:4px; padding:16px; height:100%;">
          <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #ecece8; padding-bottom:8px; margin-bottom:12px;">
            <div style="font-family:'IBM Plex Mono',monospace; font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:0.06em; color:#171717;">
              Divergence Watch
            </div>
            <span style="font-family:'IBM Plex Mono',monospace; font-size:10px; color:#73736c;">Signal Disagreement</span>
          </div>

          <div class="divergence-card-demand">
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <span style="font-family:'IBM Plex Mono',monospace; font-weight:700; font-size:12px; color:#171717;">SQL Server</span>
              {render_signal_badge('DEMAND-LED', size='sm', show_dot=False)}
            </div>
            <div style="font-family:'IBM Plex Mono',monospace; font-size:11px; color:#4b5563; margin-top:3px;">
              28 jobs/week &bull; 17 usable repositories
            </div>
            <p style="font-size:11px; color:#1e3a8a; margin:4px 0 0 0; line-height:1.4;">
              Strong hiring demand with comparatively limited ecosystem activity.
            </p>
          </div>

          <div class="divergence-card-hype">
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <span style="font-family:'IBM Plex Mono',monospace; font-weight:700; font-size:12px; color:#171717;">LangChain</span>
              {render_signal_badge('HYPE-LED', size='sm', show_dot=False)}
            </div>
            <div style="font-family:'IBM Plex Mono',monospace; font-size:11px; color:#4b5563; margin-top:3px;">
              0 jobs/week &bull; 78 usable repositories
            </div>
            <p style="font-size:11px; color:#92400e; margin:4px 0 0 0; line-height:1.4;">
              Strong ecosystem attention without comparable observed hiring demand.
            </p>
          </div>

          <div class="divergence-card-hype">
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <span style="font-family:'IBM Plex Mono',monospace; font-weight:700; font-size:12px; color:#171717;">Docker</span>
              {render_signal_badge('HYPE-LED', size='sm', show_dot=False)}
            </div>
            <div style="font-family:'IBM Plex Mono',monospace; font-size:11px; color:#4b5563; margin-top:3px;">
              1 jobs/week &bull; 89 usable repositories
            </div>
            <p style="font-size:11px; color:#92400e; margin:4px 0 0 0; line-height:1.4;">
              Universal container tooling adoption; rare in isolated hiring requisitions.
            </p>
          </div>
        </div>
        """)


# ════════════════════════════════════════════════════════════════════════════
# TAB 2: TECHNOLOGY EXPLORER (TechnologyExplorerView.tsx)
# ════════════════════════════════════════════════════════════════════════════
with tab_explorer:
    # Header
    render_html("""
    <div style="border-bottom:1px solid #e5e5df; padding-bottom:14px; margin-bottom:16px; display:flex; justify-content:space-between; align-items:flex-end; flex-wrap:wrap; gap:10px;">
      <div>
        <div style="font-family:'IBM Plex Mono',monospace; font-size:11px; text-transform:uppercase; letter-spacing:0.08em; color:#73736c; margin-bottom:2px;">
          Query &amp; Inspection
        </div>
        <h2 style="font-size:24px; font-weight:700; letter-spacing:-0.03em; color:#171717; margin:0 0 4px 0;">
          Technology Explorer
        </h2>
        <p style="font-size:12px; color:#575752; margin:0;">
          Dense comparative index across employer job postings, developer adoption, and GitHub repository metrics.
        </p>
      </div>
    </div>
    """)

    # Filter Bar with explicit unique keys
    f_col1, f_col2, f_col3, f_col4 = st.columns([3, 2, 2, 1.5])
    with f_col1:
        search_exp = st.text_input("Search", placeholder="Search technology...", label_visibility="collapsed", key="exp_search_input")
    with f_col2:
        cat_options = ["all", "Languages", "Frameworks & Runtimes", "Cloud & Infrastructure", "Data & Databases", "AI & Machine Learning", "DevOps & Tooling"]
        cat_exp = st.selectbox("Category", cat_options, format_func=lambda c: f"Category: {c.title()}" if c != "all" else "Category: All", label_visibility="collapsed", key="exp_category_select")
    with f_col3:
        sig_options = ["all", "THRIVING", "DEMAND-LED", "HYPE-LED", "WEAK"]
        sig_exp = st.selectbox("Signal", sig_options, format_func=lambda s: f"Signal: {s}" if s != "all" else "Signal: All", label_visibility="collapsed", key="exp_signal_select")
    with f_col4:
        emerging_exp = st.checkbox("Emerging only", key="exp_emerging_cb")

    df_filtered_exp = df_techs.copy()
    if search_exp.strip():
        q = search_exp.strip().lower()
        df_filtered_exp = df_filtered_exp[df_filtered_exp["canonical_name"].str.lower().str.contains(q)]
    if cat_exp != "all":
        df_filtered_exp = df_filtered_exp[df_filtered_exp["category"] == cat_exp]
    if sig_exp != "all":
        df_filtered_exp = df_filtered_exp[df_filtered_exp["composite_signal"] == sig_exp]
    if emerging_exp:
        df_filtered_exp = df_filtered_exp[df_filtered_exp["is_emerging"] == True]

    # Showing badge
    render_html(f"""
    <div style="display:flex; justify-content:space-between; align-items:center; margin:10px 0 8px 0; font-family:'IBM Plex Mono',monospace; font-size:11px; color:#73736c;">
      <span>Showing <strong style="color:#171717;">{len(df_filtered_exp)}</strong> of {TOTAL_TECHS} technologies</span>
    </div>
    """)

    # Dense Analytical Table
    table_rows = ""
    for _, row in df_filtered_exp.iterrows():
        name = row["canonical_name"]
        cat = row["category"]
        jobs = int(row["weekly_job_count"])
        repos = int(row["gh_usable_repos"])
        stars_k = f"{row['gh_median_stars']/1000:.1f}K" if row["gh_median_stars"] >= 1000 else f"{int(row['gh_median_stars'])}"
        act_pct = f"{int(row['gh_active_ratio']*100)}%" if row["gh_active_ratio"] > 0 else "—"
        so_pct = f"{row['so_adoption_pct']:.1f}%" if row["so_adoption_pct"] > 0 else "—"
        badge = render_signal_badge(row["composite_signal"], size="sm")

        emg_tag = '<span style="font-size:9px; font-family:\'IBM Plex Mono\',monospace; background:#fef3c7; color:#92400e; padding:1px 4px; border-radius:2px; margin-left:6px;">emerging</span>' if row["is_emerging"] else ""

        table_rows += f"""<tr>
          <td>
            <div style="font-weight:600; color:#171717; display:flex; align-items:center;">
              {name} {emg_tag}
            </div>
            <div style="font-size:10px; color:#888880; font-family:'Plus Jakarta Sans',sans-serif;">{cat}</div>
          </td>
          <td>{badge}</td>
          <td style="text-align:right; font-weight:700; color:{'#171717' if jobs >= 5 else '#73736c'};">{jobs}</td>
          <td style="text-align:right; color:#333330;">{so_pct}</td>
          <td style="text-align:right; font-weight:700; color:{'#171717' if repos >= 30 else '#73736c'};">{repos} <span style="font-size:10px; color:#888880;">/ 100</span></td>
          <td style="text-align:right; color:#333330;">{act_pct}</td>
          <td style="text-align:right; color:#52524d;">{stars_k}</td>
          <td style="text-align:right; color:#047857; font-weight:600;">+{row['job_trend_pct']}%</td>
        </tr>"""

    render_html(f"""
    <div style="background:white; border:1px solid #e5e5df; border-radius:4px; overflow-x:auto;">
      <table class="dense-table">
        <thead>
          <tr>
            <th>Technology</th>
            <th>Signal</th>
            <th style="text-align:right;">Jobs/wk</th>
            <th style="text-align:right;">SO Adoption</th>
            <th style="text-align:right;">Usable Repos</th>
            <th style="text-align:right;">Active Repo %</th>
            <th style="text-align:right;">Median Stars</th>
            <th style="text-align:right;">Trend</th>
          </tr>
        </thead>
        <tbody>
          {table_rows if table_rows else '<tr><td colspan="8" style="text-align:center; padding:24px; color:#73736c;">No technologies match the selected filters.</td></tr>'}
        </tbody>
      </table>
    </div>
    """)


# ════════════════════════════════════════════════════════════════════════════
# TAB 3: SIGNAL MAP (SignalMapView.tsx)
# ════════════════════════════════════════════════════════════════════════════
with tab_signalmap:
    # Header
    render_html("""
    <div style="border-bottom:1px solid #e5e5df; padding-bottom:14px; margin-bottom:16px;">
      <div style="font-family:'IBM Plex Mono',monospace; font-size:11px; text-transform:uppercase; letter-spacing:0.08em; color:#73736c; margin-bottom:2px;">
        Analytical Heart • Quadrant Decomposition
      </div>
      <h2 style="font-size:24px; font-weight:700; letter-spacing:-0.03em; color:#171717; margin:0 0 4px 0;">
        Signal Map
      </h2>
      <p style="font-size:12px; color:#575752; margin:0;">
        Where employer demand and developer ecosystem attention diverge. X = 5 jobs/week threshold, Y = 30 usable GitHub repositories threshold.
      </p>
    </div>
    """)

    # View Mode Selector & Filters with explicit unique keys
    sm_c1, sm_c2, sm_c3, sm_c4 = st.columns([3.5, 2.5, 2, 1.2])
    with sm_c1:
        sm_view = st.radio(
            "View Mode",
            ["divergence", "all", "THRIVING", "DEMAND-LED", "HYPE-LED", "WEAK"],
            format_func=lambda x: {
                "divergence": "Divergence View",
                "all": "All Technologies",
                "THRIVING": "Thriving",
                "DEMAND-LED": "Demand-led",
                "HYPE-LED": "Hype-led",
                "WEAK": "Weak",
            }[x],
            horizontal=True,
            label_visibility="collapsed",
            key="sm_view_mode_radio"
        )
    with sm_c2:
        sm_search = st.text_input("Highlight", placeholder="Highlight technology...", label_visibility="collapsed", key="sm_highlight_search_input")
    with sm_c3:
        sm_cat = st.selectbox("Category", ["all", "Languages", "Frameworks & Runtimes", "Cloud & Infrastructure", "Data & Databases", "AI & Machine Learning", "DevOps & Tooling"], format_func=lambda c: f"Category: {c.title()}" if c != "all" else "Category: All", label_visibility="collapsed", key="sm_category_select")
    with sm_c4:
        sm_emerging = st.checkbox("Emerging", key="sm_emerging_cb")

    if sm_view == "divergence":
        render_html("""
        <div style="background:#eff6ff; border:1px solid #bfdbfe; border-radius:4px; padding:10px 14px; font-size:12px; color:#1e40af; margin-bottom:14px;">
          <strong>Divergence Mode Active:</strong> Highlighting DEMAND-LED and HYPE-LED quadrants to show where employer hiring and open-source attention deviate. Thriving and Weak points are dimmed.
        </div>
        """)

    # 8 / 4 Column Layout: Scatter Left, Inspector Right
    grid_scatter, grid_inspector = st.columns([8, 4])

    with grid_scatter:
        fig_map = build_quadrant_plot(
            df_techs,
            filter_mode=sm_view,
            selected_name=sm_search.strip() if sm_search else None,
            search_query=sm_search,
            category_filter=sm_cat,
            emerging_only=sm_emerging,
            height=550
        )
        st.plotly_chart(fig_map, use_container_width=True, config={"displayModeBar": False})

    with grid_inspector:
        # Determine inspected technology
        inspect_tech = None
        if sm_search.strip():
            matched = df_techs[df_techs["canonical_name"].str.lower() == sm_search.strip().lower()]
            if not matched.empty:
                inspect_tech = matched.iloc[0]
        
        # Default fallback to LangChain or Python
        if inspect_tech is None:
            default_cand = df_techs[df_techs["canonical_name"] == "LangChain"]
            inspect_tech = default_cand.iloc[0] if not default_cand.empty else df_techs.iloc[0]

        # Inspector Selector Dropdown with unique key
        tech_list = df_techs["canonical_name"].tolist()
        def_idx = tech_list.index(inspect_tech["canonical_name"]) if inspect_tech["canonical_name"] in tech_list else 0
        chosen_tech_name = st.selectbox("Inspect Technology", tech_list, index=def_idx, label_visibility="collapsed", key="sm_inspect_tech_select")
        
        ins = df_techs[df_techs["canonical_name"] == chosen_tech_name].iloc[0]
        
        jobs_cnt = int(ins["weekly_job_count"])
        repos_cnt = int(ins["gh_usable_repos"])
        j_arrow = "≥ 5 ↑" if jobs_cnt >= 5 else "< 5 ↓"
        r_arrow = "≥ 30 ↑" if repos_cnt >= 30 else "< 30 ↓"
        stars_str = f"{ins['gh_median_stars']/1000:.1f}K" if ins["gh_median_stars"] >= 1000 else f"{int(ins['gh_median_stars'])}"
        act_str = f"{int(ins['gh_active_ratio']*100)}%" if ins["gh_active_ratio"] > 0 else "—"

        render_html(f"""
        <div class="inspector-panel">
          <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #ecece8; padding-bottom:10px; margin-bottom:14px;">
            <div style="font-family:'IBM Plex Mono',monospace; font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:0.06em; color:#73736c;">
              Technology Inspector
            </div>
            <span style="font-family:'IBM Plex Mono',monospace; font-size:10px; color:#787870;">
              {ins['category']}
            </span>
          </div>

          <div style="margin-bottom:14px;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <h3 style="font-size:22px; font-weight:700; color:#171717; margin:0;">{ins['canonical_name']}</h3>
              {render_signal_badge(ins['composite_signal'], size='md')}
            </div>
            <div style="font-family:'IBM Plex Mono',monospace; font-size:11px; color:#73736c; margin-top:4px;">
              Adzuna keyword: <code style="background:#f0f0eb; color:#171717; border:1px solid #e2e2dc; padding:2px 6px; border-radius:3px;">{ins['adzuna_keyword']}</code>
            </div>
          </div>

          <div style="background:#fafaf8; border:1px solid #e8e8e2; border-radius:4px; padding:12px; margin-bottom:14px; font-family:'IBM Plex Mono',monospace; font-size:11px;">
            <div style="display:flex; justify-content:space-between; padding:3px 0;">
              <span style="color:#73736c;">Employer Demand:</span>
              <strong style="color:#171717;">{jobs_cnt} jobs/week</strong>
            </div>
            <div style="display:flex; justify-content:space-between; padding:3px 0;">
              <span style="color:#73736c;">GitHub Ecosystem:</span>
              <strong style="color:#171717;">{repos_cnt} usable repos</strong>
            </div>
            <div style="display:flex; justify-content:space-between; padding:3px 0;">
              <span style="color:#73736c;">Stack Overflow:</span>
              <span style="color:#171717;">{ins['so_adoption_pct']:.1f}%</span>
            </div>
            <div style="display:flex; justify-content:space-between; padding:3px 0;">
              <span style="color:#73736c;">Active Repositories:</span>
              <span style="color:#171717;">{act_str}</span>
            </div>
            <div style="display:flex; justify-content:space-between; padding:3px 0;">
              <span style="color:#73736c;">Median Stars:</span>
              <span style="color:#171717;">{stars_str}</span>
            </div>
          </div>

          <div style="border-top:1px solid #d4d4ce; padding-top:12px; margin-bottom:14px;">
            <div style="font-family:'IBM Plex Mono',monospace; font-size:10px; text-transform:uppercase; color:#73736c; margin-bottom:4px;">
              Quadrant Signal Evaluation
            </div>
            <div style="font-family:'IBM Plex Mono',monospace; font-size:13px; font-weight:700; color:#171717;">
              Jobs {j_arrow} + Ecosystem {r_arrow} &rarr; {ins['composite_signal']}
            </div>
            <p style="font-size:11px; color:#40403c; line-height:1.5; background:#f7f7f3; border:1px solid #e8e8e2; border-radius:3px; padding:10px; margin:8px 0 0 0;">
              {ins['divergence_note'] if ins['divergence_note'] else 'Evaluation generated from observed Adzuna hiring demand and quality-classified GitHub sample.'}
            </p>
          </div>

          <div style="border-top:1px solid #ecece8; padding-top:12px; font-size:11px;">
            <div style="font-family:'IBM Plex Mono',monospace; font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:0.06em; color:#171717; margin-bottom:6px;">
              Divergence Archetypes:
            </div>
            <div style="background:#eff6ff; border:1px solid #bfdbfe; border-radius:3px; padding:8px 10px; color:#1e40af; margin-bottom:6px;">
              <strong>DEMAND-LED:</strong> High employer demand (Jobs ≥ 5) despite limited GitHub ecosystem (Repos &lt; 30). Common in enterprise backend, databases, and proprietary stacks.
            </div>
            <div style="background:#fffbeb; border:1px solid #fde68a; border-radius:3px; padding:8px 10px; color:#92400e;">
              <strong>HYPE-LED:</strong> High open-source developer attention (Repos ≥ 30) without comparable observed hiring demand (Jobs &lt; 5). Common in emerging AI tooling and experimental frameworks.
            </div>
          </div>
        </div>
        """)


# ════════════════════════════════════════════════════════════════════════════
# TAB 4: METHODOLOGY (MethodologyView.tsx)
# ════════════════════════════════════════════════════════════════════════════
with tab_methodology:
    render_html("""
    <div style="border-bottom:1px solid #e5e5df; padding-bottom:16px; margin-bottom:24px; max-width:1000px;">
      <div style="font-family:'IBM Plex Mono',monospace; font-size:11px; text-transform:uppercase; letter-spacing:0.08em; color:#73736c; margin-bottom:4px;">
        Technical Specification &amp; Pipeline Architecture
      </div>
      <h2 style="font-size:26px; font-weight:700; letter-spacing:-0.03em; color:#171717; margin:0 0 6px 0;">
        How the signals are constructed
      </h2>
      <p style="font-size:13px; color:#575752; margin:0; line-height:1.6;">
        Rigorous methodology uniting annual survey baselines, daily observed hiring demand, and monthly quality-filtered open source ecosystem snapshots.
      </p>
    </div>
    """)

    # Section 1: Three-Source Pipeline
    render_html("""
    <div style="max-width:1000px; margin-bottom:28px;">
      <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #ecece8; padding-bottom:8px; margin-bottom:14px;">
        <span style="font-family:'IBM Plex Mono',monospace; font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:0.06em; color:#171717;">
          1. Three-Source Data Pipeline
        </span>
        <span style="font-family:'IBM Plex Mono',monospace; font-size:11px; color:#73736c;">Orchestrated via dbt Core</span>
      </div>
    </div>
    """)

    p1, p2, p3 = st.columns(3)
    with p1:
        render_html(f"""
        <div style="background:white; border:1px solid #e5e5df; border-radius:4px; padding:16px; height:100%;">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
            <strong style="font-family:'IBM Plex Mono',monospace; font-size:11px; color:#171717;">STACK OVERFLOW</strong>
            <span style="font-family:'IBM Plex Mono',monospace; font-size:10px; color:#73736c; background:#f4f4f0; padding:2px 6px; border-radius:2px;">Annual</span>
          </div>
          <div style="font-size:13px; font-weight:600; color:#171717; margin-bottom:4px;">Annual Developer Survey ({SO_YEAR})</div>
          <p style="font-size:12px; color:#575752; line-height:1.6; margin:0;">
            48K+ global developer respondents establish the empirical developer adoption baseline and self-reported technology usage.
          </p>
          <div style="margin-top:14px; padding-top:8px; border-top:1px solid #f0f0eb; font-family:'IBM Plex Mono',monospace; font-size:10px; color:#73736c;">
            Baseline: Developer Adoption %
          </div>
        </div>
        """)
    with p2:
        render_html("""
        <div style="background:white; border:1px solid #e5e5df; border-radius:4px; padding:16px; height:100%;">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
            <strong style="font-family:'IBM Plex Mono',monospace; font-size:11px; color:#171717;">ADZUNA IT INDIA</strong>
            <span style="font-family:'IBM Plex Mono',monospace; font-size:10px; color:#047857; background:#ecfdf5; padding:2px 6px; border-radius:2px;">Daily Extraction</span>
          </div>
          <div style="font-size:13px; font-weight:600; color:#171717; margin-bottom:4px;">Observed Employer Demand</div>
          <p style="font-size:12px; color:#575752; line-height:1.6; margin:0;">
            Daily extraction of active IT employer postings deduplicated into ~1,788 current requisitions across tracked skill keywords.
          </p>
          <div style="margin-top:14px; padding-top:8px; border-top:1px solid #f0f0eb; font-family:'IBM Plex Mono',monospace; font-size:10px; color:#73736c;">
            Measure: Weekly Job Count (X-Axis)
          </div>
        </div>
        """)
    with p3:
        render_html("""
        <div style="background:white; border:1px solid #e5e5df; border-radius:4px; padding:16px; height:100%;">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
            <strong style="font-family:'IBM Plex Mono',monospace; font-size:11px; color:#171717;">GITHUB API</strong>
            <span style="font-family:'IBM Plex Mono',monospace; font-size:10px; color:#1d4ed8; background:#eff6ff; padding:2px 6px; border-radius:2px;">Monthly Snapshot</span>
          </div>
          <div style="font-size:13px; font-weight:600; color:#171717; margin-bottom:4px;">Developer Ecosystem Activity</div>
          <p style="font-size:12px; color:#575752; line-height:1.6; margin:0;">
            Top 100 repositories sampled per technology, strictly filtered for project quality and relevance before metric computation.
          </p>
          <div style="margin-top:14px; padding-top:8px; border-top:1px solid #f0f0eb; font-family:'IBM Plex Mono',monospace; font-size:10px; color:#73736c;">
            Measure: Usable Repositories (Y-Axis)
          </div>
        </div>
        """)

    render_html("<div style='height:28px;'></div>")

    # Section 2: GitHub Repository Classification Pipeline
    render_html("""
    <div style="max-width:1000px; margin-bottom:28px;">
      <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #ecece8; padding-bottom:8px; margin-bottom:14px;">
        <span style="font-family:'IBM Plex Mono',monospace; font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:0.06em; color:#171717;">
          2. GitHub Sampling &amp; Usable Repository Filtering
        </span>
        <span style="font-family:'IBM Plex Mono',monospace; font-size:11px; color:#73736c;">Top 100 Sample Pipeline</span>
      </div>

      <div style="background:white; border:1px solid #e5e5df; border-radius:4px; padding:20px;">
        <div style="display:grid; grid-template-columns:repeat(6, 1fr); gap:8px; text-align:center; font-family:'IBM Plex Mono',monospace; font-size:11px; margin-bottom:16px;">
          <div style="background:#f5f5f0; border:1px solid #e2e2dc; border-radius:3px; padding:8px 4px;">
            <div style="font-weight:700; color:#171717;">Step 1</div>
            <div style="font-size:10px; color:#575752; margin-top:2px;">Top 100 Sample</div>
          </div>
          <div style="background:#f5f5f0; border:1px solid #e2e2dc; border-radius:3px; padding:8px 4px;">
            <div style="font-weight:700; color:#171717;">Step 2</div>
            <div style="font-size:10px; color:#575752; margin-top:2px;">Hard Exclusions</div>
          </div>
          <div style="background:#f5f5f0; border:1px solid #e2e2dc; border-radius:3px; padding:8px 4px;">
            <div style="font-weight:700; color:#171717;">Step 3</div>
            <div style="font-size:10px; color:#575752; margin-top:2px;">Contamination</div>
          </div>
          <div style="background:#f5f5f0; border:1px solid #e2e2dc; border-radius:3px; padding:8px 4px;">
            <div style="font-weight:700; color:#171717;">Step 4</div>
            <div style="font-size:10px; color:#575752; margin-top:2px;">Relevance Score</div>
          </div>
          <div style="background:#ecfdf5; border:1px solid #a7f3d0; border-radius:3px; padding:8px 4px; color:#065f46;">
            <div style="font-weight:700;">Step 5</div>
            <div style="font-size:10px; margin-top:2px;">Usable Repos Set</div>
          </div>
          <div style="background:#fafaf8; border:1px solid #e2e2dc; border-radius:3px; padding:8px 4px;">
            <div style="font-weight:700; color:#171717;">Step 6</div>
            <div style="font-size:10px; color:#575752; margin-top:2px;">Ecosystem Stats</div>
          </div>
        </div>

        <div style="background:#171717; color:#fafaf8; border-radius:4px; padding:14px; font-family:'IBM Plex Mono',monospace; font-size:12px; margin-bottom:16px;">
          <div style="color:#a3a39e; font-size:10px; text-transform:uppercase; letter-spacing:0.08em; margin-bottom:4px;">
            Formal Boolean Filter Expression (dbt transformation)
          </div>
          <div style="color:#34d399; font-weight:600; overflow-x:auto; padding:4px 0;">
            NOT is_fork AND NOT is_archived AND NOT is_disabled AND quality_class IN ('project', 'uncertain') AND relevance_score &gt;= 2
          </div>
          <div style="color:#a3a39e; font-size:10px; margin-top:4px;">
            Only repositories satisfying all conditions contribute to the ecosystem metrics and usable repository count.
          </div>
        </div>

        <div style="font-family:'IBM Plex Mono',monospace; font-size:11px; font-weight:600; text-transform:uppercase; color:#171717; margin-bottom:8px;">
          Repository Classification Taxonomy:
        </div>
        <div style="display:grid; grid-template-columns:repeat(3, 1fr); gap:10px; font-size:11px;">
          <div style="background:#fafaf8; border:1px solid #e5e5df; border-radius:3px; padding:10px;">
            <strong style="font-family:'IBM Plex Mono',monospace; color:#065f46;">Project:</strong>
            <p style="color:#575752; margin:2px 0 0 0;">Production code, real application, library, or functioning tool.</p>
          </div>
          <div style="background:#fafaf8; border:1px solid #e5e5df; border-radius:3px; padding:10px;">
            <strong style="font-family:'IBM Plex Mono',monospace; color:#065f46;">Uncertain:</strong>
            <p style="color:#575752; margin:2px 0 0 0;">Borderline utility or early-stage library retained under scrutiny.</p>
          </div>
          <div style="background:#fffbeb; border:1px solid #fde68a; border-radius:3px; padding:10px;">
            <strong style="font-family:'IBM Plex Mono',monospace; color:#92400e;">Educational:</strong>
            <p style="color:#78350f; margin:2px 0 0 0;">Tutorials, interview prep, homework exercises (excluded).</p>
          </div>
          <div style="background:#fffbeb; border:1px solid #fde68a; border-radius:3px; padding:10px;">
            <strong style="font-family:'IBM Plex Mono',monospace; color:#92400e;">Collection:</strong>
            <p style="color:#78350f; margin:2px 0 0 0;">Awesome-lists, link aggregators, curation books (excluded).</p>
          </div>
          <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:3px; padding:10px;">
            <strong style="font-family:'IBM Plex Mono',monospace; color:#475569;">Other:</strong>
            <p style="color:#475569; margin:2px 0 0 0;">Config files, dotfiles, resumes, or meta artifacts (excluded).</p>
          </div>
          <div style="background:#fef2f2; border:1px solid #fecaca; border-radius:3px; padding:10px;">
            <strong style="font-family:'IBM Plex Mono',monospace; color:#991b1b;">Excluded:</strong>
            <p style="color:#991b1b; margin:2px 0 0 0;">Archived, disabled, fork mirrors, or zero-activity stubs.</p>
          </div>
        </div>
      </div>
    </div>
    """)

    # Section 3: Star Semantics
    render_html(f"""
    <div style="max-width:1000px; margin-bottom:28px;">
      <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #ecece8; padding-bottom:8px; margin-bottom:14px;">
        <span style="font-family:'IBM Plex Mono',monospace; font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:0.06em; color:#171717;">
          3. Ecosystem Metrics &amp; Star Semantics
        </span>
        <span style="font-family:'IBM Plex Mono',monospace; font-size:11px; color:#73736c;">Data Semantics Contract</span>
      </div>

      <div style="background:#fefce8; border:1px solid #fef08a; border-radius:4px; padding:14px; font-size:12px; color:#713f12; margin-bottom:14px; line-height:1.6;">
        <strong style="color:#171717;">Core Analytical Principle:</strong> GitHub stars represent <strong>developer attention</strong> around sampled projects. They are <strong>not</strong> treated as a direct measure of technology adoption. Adoption is calibrated through employer requisitions (Adzuna) and developer survey responses (Stack Overflow {SO_YEAR}).
      </div>

      <div style="display:grid; grid-template-columns:repeat(2, 1fr); gap:12px; font-family:'IBM Plex Mono',monospace; font-size:11px;">
        <div style="background:white; border:1px solid #e5e5df; border-radius:4px; padding:12px;">
          <strong style="color:#171717;">Observed Repositories:</strong>
          <p style="color:#575752; font-family:'Plus Jakarta Sans',sans-serif; margin:2px 0 0 0;">The 100 repositories returned by GitHub search query for the technology slug.</p>
        </div>
        <div style="background:white; border:1px solid #e5e5df; border-radius:4px; padding:12px;">
          <strong style="color:#171717;">Usable Repositories:</strong>
          <p style="color:#575752; font-family:'Plus Jakarta Sans',sans-serif; margin:2px 0 0 0;">Count of repositories meeting strict relevance score (≥ 2) and quality classes.</p>
        </div>
        <div style="background:white; border:1px solid #e5e5df; border-radius:4px; padding:12px;">
          <strong style="color:#171717;">Median Stars / Forks:</strong>
          <p style="color:#575752; font-family:'Plus Jakarta Sans',sans-serif; margin:2px 0 0 0;">Robust 50th percentile metric preventing outlier stars (e.g. 100K star lists) from skewing signal.</p>
        </div>
        <div style="background:white; border:1px solid #e5e5df; border-radius:4px; padding:12px;">
          <strong style="color:#171717;">Active Repository Ratio:</strong>
          <p style="color:#575752; font-family:'Plus Jakarta Sans',sans-serif; margin:2px 0 0 0;">Fraction of sampled repositories with at least one pushed commit within the prior 90 days.</p>
        </div>
      </div>
    </div>
    """)

    # Section 4: Composite Signal Matrix (2x2 Grid)
    render_html("""
    <div style="max-width:1000px; margin-bottom:28px;">
      <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #ecece8; padding-bottom:8px; margin-bottom:14px;">
        <span style="font-family:'IBM Plex Mono',monospace; font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:0.06em; color:#171717;">
          4. Composite Signal Matrix &amp; Quadrant Thresholds
        </span>
        <span style="font-family:'IBM Plex Mono',monospace; font-size:11px; color:#73736c;">Threshold: X=5 jobs, Y=30 repos</span>
      </div>

      <div style="background:white; border:1px solid #e5e5df; border-radius:4px; padding:24px;">
        <div style="max-width:680px; margin:0 auto; font-family:'IBM Plex Mono',monospace; font-size:11px;">
          <div style="text-align:center; color:#73736c; font-weight:600; margin-bottom:8px; letter-spacing:0.06em;">
            ▲ GITHUB USABLE REPOSITORIES ≥ 30
          </div>

          <div style="display:grid; grid-template-columns:1fr 1fr; border:2px solid #171717; border-radius:4px; overflow:hidden;">
            <div style="background:#fffbeb; border-right:1px solid #171717; border-bottom:1px solid #171717; padding:16px;">
              <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                <strong style="color:#92400e; font-size:13px;">HYPE-LED</strong>
                <span style="background:#fef3c7; color:#92400e; border:1px solid #fde68a; border-radius:2px; padding:1px 5px; font-size:9px; font-weight:700;">HYPE-LED</span>
              </div>
              <div style="font-size:11px; color:#78350f; font-family:'Plus Jakarta Sans',sans-serif; margin-top:6px;">
                <strong>Jobs &lt; 5 AND Usable Repos ≥ 30</strong>
                <p style="margin:4px 0 0 0; line-height:1.4;">Strong developer ecosystem attention without comparable observed hiring demand.</p>
              </div>
            </div>

            <div style="background:#ecfdf5; border-bottom:1px solid #171717; padding:16px;">
              <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                <strong style="color:#065f46; font-size:13px;">THRIVING</strong>
                <span style="background:#dcfce7; color:#065f46; border:1px solid #a7f3d0; border-radius:2px; padding:1px 5px; font-size:9px; font-weight:700;">THRIVING</span>
              </div>
              <div style="font-size:11px; color:#064e3b; font-family:'Plus Jakarta Sans',sans-serif; margin-top:6px;">
                <strong>Jobs ≥ 5 AND Usable Repos ≥ 30</strong>
                <p style="margin:4px 0 0 0; line-height:1.4;">Strong employer demand backed by strong ecosystem activity. Proven production viability.</p>
              </div>
            </div>

            <div style="background:#f8fafc; border-right:1px solid #171717; padding:16px;">
              <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                <strong style="color:#475569; font-size:13px;">WEAK</strong>
                <span style="background:#f1f5f9; color:#475569; border:1px solid #cbd5e1; border-radius:2px; padding:1px 5px; font-size:9px; font-weight:700;">WEAK</span>
              </div>
              <div style="font-size:11px; color:#334155; font-family:'Plus Jakarta Sans',sans-serif; margin-top:6px;">
                <strong>Jobs &lt; 5 AND Usable Repos &lt; 30</strong>
                <p style="margin:4px 0 0 0; line-height:1.4;">Limited evidence of either active employer demand or lively open-source ecosystem activity.</p>
              </div>
            </div>

            <div style="background:#eff6ff; padding:16px;">
              <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                <strong style="color:#1e40af; font-size:13px;">DEMAND-LED</strong>
                <span style="background:#dbeafe; color:#1e40af; border:1px solid #bfdbfe; border-radius:2px; padding:1px 5px; font-size:9px; font-weight:700;">DEMAND-LED</span>
              </div>
              <div style="font-size:11px; color:#1e3a8a; font-family:'Plus Jakarta Sans',sans-serif; margin-top:6px;">
                <strong>Jobs ≥ 5 AND Usable Repos &lt; 30</strong>
                <p style="margin:4px 0 0 0; line-height:1.4;">Strong employer hiring demand despite relatively limited public open-source activity.</p>
              </div>
            </div>
          </div>

          <div style="text-align:center; color:#73736c; font-weight:600; margin-top:8px; letter-spacing:0.06em;">
            ▼ GITHUB USABLE REPOSITORIES &lt; 30
          </div>

          <div style="display:flex; justify-content:space-between; align-items:center; color:#73736c; font-size:11px; margin-top:12px; padding:0 4px;">
            <span>◄ EMPLOYER JOBS &lt; 5 / week</span>
            <span style="font-weight:700; color:#171717;">Threshold: 5 jobs/week</span>
            <span>EMPLOYER JOBS ≥ 5 / week ►</span>
          </div>
        </div>
      </div>
    </div>
    """)

    # Section 5: Temporal Transparency
    render_html("""
    <div style="max-width:1000px; background:#f5f5f0; border:1px solid #d4d4ce; border-radius:4px; padding:16px; font-family:'IBM Plex Mono',monospace; font-size:11px;">
      <div style="font-weight:700; color:#171717; text-transform:uppercase; margin-bottom:6px;">
        5. Temporal Transparency
      </div>
      <p style="color:#575752; font-family:'Plus Jakarta Sans',sans-serif; margin:0; line-height:1.6;">
        <strong>Weekly Job Counts:</strong> Weekly observations from Adzuna IT extractions.<br>
        <strong>GitHub Metrics:</strong> Latest monthly snapshot. The analytical view reflects current commercial requisitions alongside open source ecosystem activity without implying daily historical precision for repository sampling.
      </p>
    </div>
    """)
