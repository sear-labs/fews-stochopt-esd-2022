"""Stage 7: the cleaned output everything downstream reads.

Archetype P separates *raw output* — whatever the solver dumped, gitignored —
from *cleaned output*, which is tidy, long-format and committed, and is the only
thing analysis and figures are allowed to read.

That separation matters here for a reason worth naming. The raw output is
**135 MB** of per-run, per-year solver detail. The archetype's boundary says
committed cleaned output "assumes it stays small... around 10 MB", and 135 MB is
plainly not. The resolution is not to abandon the pattern or to compress: it is
that the per-run detail is *raw*, and what everything actually reads is an
aggregate of it that comes to a few tens of kilobytes. Committing the right layer
is what keeps the repository working from a clean clone.

**Figures read cleaned output, never raw.** A figure that re-derives per-year
means from the solver dump is re-implementing this module, and the second copy is
the one that drifts.

Everything here is long format — one row per observation, a `variable` column and
a `value` column — because a wide table with one column per scenario has to be
edited every time a scenario is added, and nothing notices when it is not.
"""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import pandas as pd

from fews_stochopt.aggregate import SCENARIOS, scenario_stats, value_of_information
from fews_stochopt.config import Config, repo_root
from fews_stochopt.data import climate_of_run, load_precipitation
from fews_stochopt.model import ScenarioResult

CLEAN = "clean"

# The per-year quantities worth carrying forward. `crop_yield` is per hectare;
# the rest are the farm totals the model works in.
YEARLY = ("crop_yield", "water", "elc", "irrigation", "alt_water")


def clean_dir(root: Path | None = None) -> Path:
    return (root or repo_root()) / "results" / CLEAN


def scenario_table(
    cfg: Config, results: dict[str, dict[str, ScenarioResult]]
) -> pd.DataFrame:
    """Per site and scenario: the Table 5 statistics, long."""
    rows = []
    for site, by_scenario in results.items():
        for scenario in SCENARIOS:
            stats = asdict(scenario_stats(by_scenario[scenario]))
            stats.pop("sim")
            for metric, value in stats.items():
                rows.append(
                    {
                        "site": site,
                        "label": cfg.site(site).label,
                        "scenario": scenario,
                        "variable": metric,
                        "value": float(value),
                    }
                )
    return pd.DataFrame(rows)


def value_table(
    cfg: Config, results: dict[str, dict[str, ScenarioResult]]
) -> pd.DataFrame:
    """Table 4, long, with the published figure beside each value."""
    published = {
        ("EP", "Value_of_Known_Weather"): 10396.3181015145,
        ("EP", "Value_of_Perfect_Information"): 108725.141709509,
        ("EP", "Value_of_Stochastic_Solution"): 0.488689677613507,
        ("EP", "Value_of_Known_Climate"): 2345266.78510709 - 2246937.96149909,
        ("DML", "Value_of_Known_Weather"): 11740.0305519786,
        ("DML", "Value_of_Perfect_Information"): 76606.0080918825,
        ("DML", "Value_of_Stochastic_Solution"): 940.899927688976,
        ("DML", "Value_of_Known_Climate"): 1964087.20890134 - 1899221.23136143,
    }
    rows = []
    for site, by_scenario in results.items():
        row = value_of_information(cfg, site, by_scenario)
        for quantity, value in row.items():
            if quantity == "Climate_Probability":
                continue
            rows.append(
                {
                    "site": site,
                    "label": cfg.site(site).label,
                    "variable": quantity,
                    "value": float(value),
                    "published": published[(site, quantity)],
                    "difference": float(value) - published[(site, quantity)],
                }
            )
    return pd.DataFrame(rows)


def yearly_table(
    cfg: Config, results: dict[str, dict[str, ScenarioResult]]
) -> pd.DataFrame:
    """Per site, scenario, year and quantity: the mean over runs. Long.

    This is the aggregate that replaces 135 MB of per-run detail. Every figure
    reads it and nothing reads the detail.
    """
    frames = []
    for site, by_scenario in results.items():
        for scenario in SCENARIOS:
            detail = by_scenario[scenario].detail
            means = detail.groupby("year")[list(YEARLY)].mean().reset_index()
            long = means.melt(id_vars="year", var_name="variable", value_name="value")
            long.insert(0, "scenario", scenario)
            long.insert(0, "label", cfg.site(site).label)
            long.insert(0, "site", site)
            frames.append(long)
    return pd.concat(frames, ignore_index=True)


def climate_table(cfg: Config, results: dict[str, dict[str, ScenarioResult]]) -> pd.DataFrame:
    """Per site and climate: mean precipitation and mean profit under perfect information.

    This is what shows that a wetter climate does not always earn more -- the
    yield curve peaks near 72 cm and the farm cannot shed water.
    """
    from fews_stochopt.model import PERFECT_INFORMATION

    rows = []
    for site, by_scenario in results.items():
        mapping = climate_of_run(cfg.site(site))
        rain = load_precipitation(cfg, site)
        rain = rain.assign(climate=rain["run"].map(mapping))
        profit = by_scenario[PERFECT_INFORMATION].profit
        profit = profit.assign(climate=profit["run"].map(mapping))
        precip = rain.groupby("climate")["precip"].mean()
        earned = profit.groupby("climate")["profit"].mean()
        runs = profit.groupby("climate").size()
        for climate in sorted(precip.index):
            rows.append(
                {
                    "site": site,
                    "label": cfg.site(site).label,
                    "climate": int(climate),
                    "runs": int(runs[climate]),
                    "mean_precip_cm": float(precip[climate]),
                    "mean_profit_perfect_information": float(earned[climate]),
                }
            )
    return pd.DataFrame(rows)


def precipitation_table(cfg: Config, regenerated: dict[str, pd.DataFrame] | None = None) -> pd.DataFrame:
    """Share of run-years in each weather state, committed against regenerated.

    The regenerated column is what `markov.simulate` produces. It is not the
    committed sample and cannot be -- the original's RNG state was never
    recorded -- so the check is distributional.
    """
    rows = []
    for site in cfg.sites:
        committed = load_precipitation(cfg, site)["precip"]
        shares = committed.value_counts(normalize=True).sort_index()
        fresh = None
        if regenerated and site in regenerated:
            fresh = regenerated[site]["precip"].value_counts(normalize=True)
        for precip, share in shares.items():
            rows.append(
                {
                    "site": site,
                    "label": cfg.site(site).label,
                    "precip_cm": float(precip),
                    "committed_share": float(share),
                    "regenerated_share": (
                        float(fresh.get(precip, 0.0)) if fresh is not None else None
                    ),
                }
            )
    return pd.DataFrame(rows)


def write_all(
    cfg: Config,
    results: dict[str, dict[str, ScenarioResult]],
    regenerated: dict[str, pd.DataFrame] | None = None,
    root: Path | None = None,
    log=print,
) -> dict[str, Path]:
    """Write every cleaned-output table and report what went where."""
    out = clean_dir(root)
    out.mkdir(parents=True, exist_ok=True)
    tables = {
        "scenario_stats.csv": scenario_table(cfg, results),
        "value_of_information.csv": value_table(cfg, results),
        "yearly.csv": yearly_table(cfg, results),
        "climates.csv": climate_table(cfg, results),
        "precipitation_states.csv": precipitation_table(cfg, regenerated),
    }
    written = {}
    total = 0
    for name, frame in tables.items():
        if frame.empty:
            raise ValueError(f"cleaned output {name} is empty; nothing to write")
        path = out / name
        frame.to_csv(path, index=False)
        total += path.stat().st_size
        written[name] = path
        log(f"  {name:28} {len(frame):>6} rows  {path.stat().st_size / 1024:>7.1f} KB")
    log(f"  {'total':28} {'':>6}       {total / 1024:>7.1f} KB")
    return written
