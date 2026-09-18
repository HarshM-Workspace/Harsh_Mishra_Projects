"""
dbt_assets.py
-------------
Dagster-dbt integration — wraps dbt models as Dagster software-defined assets.

Uses dagster-dbt to automatically generate an asset per dbt model,
preserving the dbt dependency graph (staging → intermediate → marts).

The dbt assets depend on `consolidated_parquet` (produced by raw_assets.py),
ensuring dbt only runs after fresh raw data is available.
"""

from pathlib import Path

from dagster import AssetExecutionContext, AssetKey
from dagster_dbt import DbtCliResource, dbt_assets, DbtProject

# dbt project root
_DBT_PROJECT_DIR = Path(__file__).parent.parent.parent / "dbt"

dbt_project = DbtProject(
    project_dir=_DBT_PROJECT_DIR,
    profiles_dir=_DBT_PROJECT_DIR,
)
dbt_project.prepare_if_dev()

# This generates one Dagster asset per dbt model automatically.
# non_argument_deps ensures dbt only runs after consolidated_parquet
# (raw → parquet preparation) has completed, making the Dagster graph complete.
@dbt_assets(
    manifest=dbt_project.manifest_path,
    non_argument_deps={AssetKey("consolidated_parquet")},
)
def labor_market_dbt_assets(context: AssetExecutionContext, dbt: DbtCliResource):
    yield from dbt.cli(["run", "--full-refresh"], context=context).stream()

