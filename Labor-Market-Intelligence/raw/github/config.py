"""
config.py
---------
All tunable thresholds and scoring weights for the GitHub ecosystem extractor.

Keep weights here — not scattered inside classifier.py or snapshot.py —
so that post-validation tuning is a single-file edit.
"""

# ---------------------------------------------------------------------------
# Hard-filter flags — these immediately exclude a repo from usable set
# (kept in raw but marked excluded before any scoring)
# ---------------------------------------------------------------------------
HARD_EXCLUDE_FLAGS = ("fork", "archived", "disabled")

# ---------------------------------------------------------------------------
# Contamination keyword weights
# Positive = educational/collection signal (bad for quality score)
# Applied to the concatenated searchable text: name + description + topics
#
# Tuning guide:
#   Strong indicator  → weight ≥ 3
#   Medium indicator  → weight 2
#   Weak indicator    → weight 1
#   Context-dependent → 0.5
# ---------------------------------------------------------------------------
CONTAMINATION_WEIGHTS: dict[str, float] = {
    # Strong collection signals
    "awesome-list":           4.0,
    "awesome_list":           4.0,
    "curated":                3.0,
    "resource-collection":    3.5,
    "resource_collection":    3.5,
    "resources":              2.0,
    "awesome":                2.5,
    "collection":             2.0,
    "collections":            2.0,
    "books":                  2.0,
    "book":                   1.5,

    # Strong educational signals
    "tutorial":               3.0,
    "tutorials":              3.0,
    "course":                 3.0,
    "courses":                3.0,
    "learning":               2.5,
    "learn":                  2.0,
    "education":              3.0,
    "educational":            3.0,
    "notes":                  2.5,
    "note":                   1.5,
    "interview":              2.5,
    "interview-questions":    3.0,
    "interview_questions":    3.0,
    "interview-preparation":  3.0,
    "practice":               2.0,
    "beginner":               2.0,
    "100-days":               3.5,
    "30-days":                3.0,
    "cheatsheet":             2.5,
    "cheat-sheet":            2.5,
    "roadmap":                2.0,
    "study":                  1.5,
    "exercises":              1.5,

    # Weak signals — don't reject on these alone
    "examples":               0.5,
    "sample":                 0.5,
    "demo":                   0.5,
    "starter":                0.5,
    "template":               0.5,
}

# ---------------------------------------------------------------------------
# Positive quality signals — offset weak contamination scores
# Applied to structured fields, not free text
# ---------------------------------------------------------------------------
QUALITY_POSITIVE: dict[str, float] = {
    "has_description":     1.5,   # repo has a non-empty description
    "has_topics":          1.5,   # repo has at least 1 GitHub topic tag
    "recent_push":         1.0,   # pushed_at within ACTIVE_WINDOW_DAYS
    "high_star_count":     0.5,   # stargazers_count > STAR_SIGNAL_THRESHOLD
}

# ---------------------------------------------------------------------------
# Quality class thresholds
# contamination_score → quality_class
#
# Score = sum of contamination weights from matched keywords.
# Negative offsets from positive signals reduce the score.
# ---------------------------------------------------------------------------
QUALITY_THRESHOLDS: dict[str, float] = {
    "educational":  5.0,   # score >= this → educational
    "collection":   5.0,   # score >= this with 'awesome'/'curated' dominant → collection
    "uncertain":    2.0,   # score in [uncertain, educational) → uncertain
    # below uncertain threshold → project (or other if no description/topics)
}

# Minimum stars to get the high_star_count positive signal
STAR_SIGNAL_THRESHOLD: int = 500

# ---------------------------------------------------------------------------
# Technology relevance scoring weights
# ---------------------------------------------------------------------------
RELEVANCE_WEIGHTS: dict[str, float] = {
    "language_exact_match":    4.0,  # repo.language == target language
    "topic_exact_match":       3.0,  # per matching topic slug
    "name_canonical_match":    3.0,  # canonical_name appears in repo name (case-insensitive)
    "name_alias_match":        2.0,  # alias appears in repo name
    "desc_canonical_match":    1.5,  # canonical_name in description
    "desc_alias_match":        1.0,  # alias in description
}

# Relevance score needed for a repo to be "usable" (pass filter)
RELEVANCE_THRESHOLD: float = 2.0

# ---------------------------------------------------------------------------
# Activity window — repos with pushed_at within this many days are "active"
# Must be consistent across all snapshots for active_repository_ratio to mean anything
# ---------------------------------------------------------------------------
ACTIVE_WINDOW_DAYS: int = 180

# ---------------------------------------------------------------------------
# Ecosystem state thresholds
# Used to label snapshot comparisons with a high-level state string
# Based on delta_usable_repositories and delta_median_stars
# ---------------------------------------------------------------------------
ECOSYSTEM_STATES = {
    # (delta_usable_repos_pct, delta_median_stars_pct) → state
    "thriving":   {"min_repos_delta": 0.10,  "min_stars_delta": 0.10},
    "growing":    {"min_repos_delta": 0.02,  "min_stars_delta": 0.02},
    "stable":     {"min_repos_delta": -0.02, "min_stars_delta": -0.02},
    "mature":     {"min_repos_delta": -0.05, "min_stars_delta": 0.0},   # stars holding, repos flat/shrinking
    "weakening":  {"min_repos_delta": -0.10, "min_stars_delta": -0.05},
    "declining":  {"min_repos_delta": -0.20, "min_stars_delta": -0.10},
}

# ---------------------------------------------------------------------------
# GitHub API settings
# ---------------------------------------------------------------------------
GITHUB_API_BASE = "https://api.github.com"
REPOS_PER_TECH = 100          # Top 100 per technology per snapshot — do not increase without documented reason
# GitHub Search API (/search/repositories) has a dedicated limit of 30 requests/min
# (distinct from the 5,000 req/hr core API limit). Buffer must be <= 5 to avoid sleeping on every request.
RATE_LIMIT_BUFFER = 3          # pause if remaining requests fall below this (out of 30)
RATE_LIMIT_SLEEP_SECONDS = 60  # fallback sleep duration if reset header missing
API_TIMEOUT = 15               # seconds per request
