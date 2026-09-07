"""Loading `config.yaml`, and the derived coefficients the model actually uses.

Two things happen here that are worth naming.

**Paths.** This repository is run from a checkout, not from a wheel: it needs the
committed precipitation files and a Gurobi licence, neither of which travels in a
package install. `repo_root()` therefore resolves the checkout the package was
installed from, and says so loudly if it cannot -- rather than returning a path
that only happens to be right on the machine that built it, which is the failure
Part 6 of the code standard records.

**Folding.** The yield function is written in `config.yaml` with every salinity
term spelled out, exactly as it appears in the notebooks and in Dinar et al.
(1991). The model needs it as a quadratic in water depth alone. `_fold_yield`
does that collapse once, and `tests/test_invariants.py` checks the folded form
against the expression as written, so the two cannot drift apart in silence.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

CONFIG_ENV_VAR = "FEWS_STOCHOPT_CONFIG"


def repo_root() -> Path:
    """The checkout this package was installed from.

    `src/fews_stochopt/config.py` -> `src/fews_stochopt` -> `src` -> the root.
    """
    root = Path(__file__).resolve().parents[2]
    if not (root / "config.yaml").exists():
        raise RuntimeError(
            f"cannot find config.yaml above {__file__}. This package is meant to be "
            f"installed from a checkout (pip install -e .) because it reads the "
            f"committed precipitation files, which a wheel does not carry. Set "
            f"{CONFIG_ENV_VAR} to the config file if it lives elsewhere."
        )
    return root


def config_path() -> Path:
    override = os.environ.get(CONFIG_ENV_VAR)
    if override:
        p = Path(override)
        if not p.exists():
            raise FileNotFoundError(f"{CONFIG_ENV_VAR}={override} does not exist")
        return p
    return repo_root() / "config.yaml"


@dataclass(frozen=True)
class YieldCoeffs:
    """Crop yield as `a0 + a1*w + a2*w**2`, with w the water depth in cm."""

    a0: float
    a1: float
    a2: float

    def __call__(self, water: float) -> float:
        return self.a0 + self.a1 * water + self.a2 * water * water


@dataclass(frozen=True)
class Site:
    key: str
    label: str
    precipitation_file: str
    climate_blocks: tuple[tuple[int, int], ...]
    climate_probabilities: tuple[float, ...]
    expected_value_rain: tuple[float, ...]


class Config:
    """Parsed `config.yaml`, plus the coefficients derived from it."""

    def __init__(self, raw: dict[str, Any], source: Path):
        self.raw = raw
        self.source = source

        c = raw["conversions"]
        f = raw["farm"]
        w = raw["water"]
        e = raw["electricity"]

        self.years: int = raw["horizon"]["years"]
        self.runs: int = raw["horizon"]["runs"]

        self.hectares: float = f["hectares"]
        self.crop_price: float = f["crop_price_per_tonne"]

        # $ per cm of alternative-water capacity, over the whole farm.
        self.cost_alt_water: float = (
            w["alt_capacity_dollars_per_gal_day"]
            / w["days_per_year"]
            / c["cm3_per_gal"]
            * c["cm2_per_ha"]
            * f["hectares"]
        )
        # kWh needed per cm of alternative water.
        self.alt_water_elc: float = (
            w["alt_kwh_per_kgal"]
            / 1000
            * c["gal_per_acre_ft"]
            / c["cm_per_ft"]
            * c["acre_per_ha"]
            * f["hectares"]
        )
        # $ per cm of irrigation water.
        self.cost_irrigation_water: float = (
            w["irrigation_dollars_per_acre_in"]
            / c["cm_per_in"]
            * c["acre_per_ha"]
            * f["hectares"]
        )
        # kWh needed per cm of irrigation water.
        self.irrigation_water_elc: float = (
            w["irrigation_kwh_per_kgal"]
            / 1000
            * c["gal_per_acre_ft"]
            / c["cm_per_ft"]
            * c["acre_per_ha"]
            * f["hectares"]
        )
        self.max_irrigation_water: float = w["irrigation_limit_ft"] * c["cm_per_ft"]

        self.cost_alt_elc: float = e["alt_capacity_dollars_per_kw"]
        self.cost_utility_elc: float = e["utility_dollars_per_kwh"]
        # kWh available per kW of installed capacity over one growing season.
        self.alt_elc_yield: float = (
            e["solar_capacity_factor"]
            * c["hours_per_month"]
            * c["growing_season_months"]
        )

        self.yield_coeffs = self._fold_yield(raw["yield_function"])

        ws = raw["weather_states"]
        # Rounded to two decimals, which is not cosmetic. The original converted
        # states to numbers through `gsub('w2', as.character(w2p), precips)`, and
        # R's as.character() gives the shortest form within 15 significant digits
        # -- so the committed files hold exactly 26.67, while the unrounded
        # product is 26.669999999999998. Without the round-trip, comparing a
        # state to a value from those files by equality finds no matches at all,
        # and a check written on that comparison reports its own arithmetic
        # rather than the data.
        self.weather_states: dict[str, float] = {
            k: round(v * c["cm_per_in"] * ws["rainfall_days_fraction"], 2)
            for k, v in ws["inches"].items()
        }

        self.sites: dict[str, Site] = {
            key: Site(
                key=key,
                label=s["label"],
                precipitation_file=s["precipitation_file"],
                climate_blocks=tuple((a, b) for a, b in s["climate_blocks"]),
                climate_probabilities=tuple(s["climate_probabilities"]),
                expected_value_rain=tuple(float(x) for x in s["expected_value_rain"]),
            )
            for key, s in raw["sites"].items()
        }

        self.solver: dict[str, Any] = raw["solver"]
        self.tolerances: dict[str, float] = {
            k: float(v) for k, v in raw["tolerances"].items()
        }

    @staticmethod
    def _fold_yield(y: dict[str, float]) -> YieldCoeffs:
        """Collapse the salinity terms, which are fixed, into a0 and a1."""
        s = y["soil_salinity_ds_per_m"]
        sw = y["water_salinity_ds_per_m"]
        a0 = (
            y["intercept"]
            + y["water_salinity"] * sw
            + y["water_salinity_squared"] * sw * sw
            + y["soil_salinity"] * s
            + y["soil_salinity_squared"] * s * s
            + y["water_salinity_x_soil_salinity"] * sw * s
        )
        a1 = (
            y["water"]
            + y["water_x_water_salinity"] * sw
            + y["water_x_soil_salinity"] * s
        )
        return YieldCoeffs(a0=a0, a1=a1, a2=y["water_squared"])

    def site(self, key: str) -> Site:
        try:
            return self.sites[key]
        except KeyError:
            raise KeyError(
                f"unknown site {key!r}; config.yaml defines {sorted(self.sites)}"
            ) from None

    def precipitation_path(self, site: str) -> Path:
        return repo_root() / self.site(site).precipitation_file

    def digest(self) -> str:
        """A stable hash of the whole configuration, for output provenance."""
        blob = json.dumps(self.raw, sort_keys=True, default=str).encode()
        return hashlib.sha256(blob).hexdigest()[:16]

    def solve_digest(self) -> str:
        """A hash of only the parts that can change a solution.

        `tolerances` is excluded deliberately. It says how closely a result must
        match a published figure; it does not enter any model. Folding it in
        would discard eight solved scenarios -- seven minutes of work -- every
        time somebody adjusted a check, which is how a cache teaches people to
        pass `--force` by reflex and stops being a cache at all.
        """
        relevant = {k: v for k, v in self.raw.items() if k != "tolerances"}
        blob = json.dumps(relevant, sort_keys=True, default=str).encode()
        return hashlib.sha256(blob).hexdigest()[:16]


@lru_cache(maxsize=1)
def load_config(path: str | os.PathLike[str] | None = None) -> Config:
    p = Path(path) if path is not None else config_path()
    with open(p, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    return Config(raw, p)
