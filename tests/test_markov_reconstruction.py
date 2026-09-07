"""The committed reconstruction still matches what the script produces.

`reference/reconstructed/` holds an estimate of `trans_matrix.csv`, the input that
was lost before this repository was split out. A generated artifact and the script
that generates it drift exactly as fast as two pasted copies, and for the same
reason -- nobody compares them. This is that comparison.

Proven to fire: perturbing one cell of the committed matrix by 1e-6 turns
`--check` red and names the file. See `docs/reproduction-notes.md`.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fews_stochopt.config import load_config  # noqa: E402
from fews_stochopt.markov import pooled_reconstruct, reconstruct  # noqa: E402

RECONSTRUCTED = ROOT / "reference" / "reconstructed"


def test_committed_reconstruction_is_not_stale():
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "reconstruct_markov.py"), "--check"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        f"reconstruct_markov.py --check exited {proc.returncode}\n"
        f"--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"
    )
    assert "matches" in proc.stdout, f"unexpected output: {proc.stdout!r}"


def test_the_committed_files_exist():
    """Guards against the check above passing over nothing."""
    files = sorted(RECONSTRUCTED.glob("*.csv"))
    assert len(files) == 3, f"expected 3 CSVs in {RECONSTRUCTED}, found {len(files)}"


def test_rows_within_a_climate_are_homogeneous():
    """The estimate's central finding, asserted rather than described.

    Within a climate every transition row is the same to within sampling error:
    the chain has no memory, and each year is an independent draw from that
    climate's weather distribution. The pooled matrix -- which is what fills the
    two rows no run ever visits -- is only defensible because of this.
    """
    cfg = load_config()
    for site in cfg.sites:
        _, provenance = pooled_reconstruct(cfg, site)
        assert len(provenance) == 4, f"{site}: expected 4 climates"
        assert provenance["homogeneous_within_3_se"].all(), (
            f"{site}: at least one climate's rows are not homogeneous, so the "
            f"pooled matrix rests on an assumption the data contradicts:\n"
            f"{provenance.to_string(index=False)}"
        )


def test_the_two_sites_agree_on_the_underlying_matrix():
    """EP and DML are independent samples; their estimates should coincide.

    This is the strongest available evidence that the reconstruction recovers the
    original rather than the sample. The two sets of draws were generated in
    different R sessions from the same matrix, so an estimate that depended on the
    sample would not agree across them.
    """
    cfg = load_config()
    ep, _ = pooled_reconstruct(cfg, "EP")
    dml, _ = pooled_reconstruct(cfg, "DML")
    difference = np.abs(ep.to_numpy() - dml.to_numpy())
    assert difference.max() < 0.02, (
        f"the two sites' reconstructions differ by up to {difference.max():.4f}, "
        f"more than sampling error explains"
    )


def test_unidentified_rows_are_recorded_not_invented():
    """A state nobody visits gets NaN in the row-wise estimate, never zeros.

    Zeros would assert those transitions impossible, which the data does not say.
    Both sites have exactly two such rows: the driest climate never reaches the
    wettest state, and the wettest never reaches the driest.
    """
    cfg = load_config()
    for site in cfg.sites:
        matrix, provenance = reconstruct(cfg, site)
        unidentified = provenance.loc[~provenance["identified"], "state"].tolist()
        assert unidentified == [f"c1{'w5'}", f"c4{'w1'}"], (
            f"{site}: unidentified rows are {unidentified}, expected c1w5 and c4w1"
        )
        for state in unidentified:
            # NaN within the state's own climate block. The off-diagonal blocks
            # are zero for every row -- a run never changes climate -- so the
            # unidentified part is the 5 columns of its own climate.
            climate = state[:2]
            block = [c for c in matrix.columns if c.startswith(climate)]
            assert len(block) == 5
            assert matrix.loc[state, block].isna().all(), (
                f"{site}: row {state} has no observations but is not NaN"
            )
            others = [c for c in matrix.columns if not c.startswith(climate)]
            assert (matrix.loc[state, others] == 0).all(), (
                f"{site}: row {state} has non-zero mass outside its own climate"
            )
        identified = provenance.loc[provenance["identified"], "state"]
        assert len(identified) == 18
        for state in identified:
            assert matrix.loc[state].sum() == pytest.approx(1.0, rel=1e-12)
