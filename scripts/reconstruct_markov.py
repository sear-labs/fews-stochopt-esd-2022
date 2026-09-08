"""Rebuild the weather transition matrix that was lost before the split.

    python scripts/reconstruct_markov.py            # write reference/reconstructed/
    python scripts/reconstruct_markov.py --check     # verify the committed copy

`trans_matrix.csv` is read by `archive/stage2-r/markov_chain.Rmd` and by both
`FM * MC.Rmd` reports, and exists nowhere. It is estimated here from the
committed precipitation draws, which is possible because precipitation takes only
five distinct values, so the state sequence is recoverable exactly.

The output is committed under `reference/reconstructed/`, and `--check` is what
makes that safe: a build script and its output drift exactly as fast as two
pasted copies, and for the same reason -- nobody compares them. `--check` is that
comparison, and `tests/test_markov_reconstruction.py` runs it.

See `src/fews_stochopt/markov.py` for what the estimate can and cannot recover.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from fews_stochopt.config import load_config, repo_root  # noqa: E402
from fews_stochopt.markov import pooled_reconstruct, reconstruct  # noqa: E402

OUT = repo_root() / "reference" / "reconstructed"


def build(cfg) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    matrices: dict[str, pd.DataFrame] = {}
    rows = []
    for site in cfg.sites:
        pooled, pooled_prov = pooled_reconstruct(cfg, site)
        _, rowwise_prov = reconstruct(cfg, site)
        matrices[site] = pooled
        unidentified = rowwise_prov.loc[~rowwise_prov["identified"], "state"].tolist()
        for _, r in pooled_prov.iterrows():
            rows.append(
                {
                    "site": site,
                    **r.to_dict(),
                    "unidentified_rows": ";".join(
                        s for s in unidentified if s.startswith(f"c{int(r['climate'])}")
                    ),
                }
            )
    return matrices, pd.DataFrame(rows)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument(
        "--check",
        action="store_true",
        help="compare against the committed copy instead of writing it",
    )
    args = p.parse_args(argv)

    cfg = load_config()
    matrices, provenance = build(cfg)

    if not provenance["homogeneous_within_3_se"].all():
        print(
            "the rows of at least one climate are NOT homogeneous, so the pooled "
            "matrix rests on an assumption the data contradicts. Refusing to write it.",
            file=sys.stderr,
        )
        print(provenance.to_string(index=False), file=sys.stderr)
        return 2

    targets = {
        **{OUT / f"trans_matrix_{s}.csv": m for s, m in matrices.items()},
        OUT / "provenance.csv": provenance,
    }

    if args.check:
        missing, differing = [], []
        for path, want in targets.items():
            if not path.exists():
                missing.append(path.name)
                continue
            index_col = 0 if path.name.startswith("trans_matrix") else None
            got = pd.read_csv(path, index_col=index_col)
            if not _same(got, want):
                differing.append(path.name)
        if missing or differing:
            print(
                f"committed reconstruction is stale -- missing {missing}, "
                f"differing {differing}. Re-run without --check.",
                file=sys.stderr,
            )
            return 1
        print(f"committed reconstruction matches: {len(targets)} file(s)")
        return 0

    OUT.mkdir(parents=True, exist_ok=True)
    for path, frame in targets.items():
        frame.to_csv(path, index=path.name.startswith("trans_matrix"))
        print(f"wrote {path}")
    print()
    print(provenance.to_string(index=False))
    return 0


def _same(got: pd.DataFrame, want: pd.DataFrame) -> bool:
    if list(got.columns) != list(want.columns):
        return False
    if len(got) != len(want):
        return False
    for col in want.columns:
        a, b = got[col], want[col]
        if pd.api.types.is_numeric_dtype(b) and pd.api.types.is_numeric_dtype(a):
            if not np.allclose(a.to_numpy(float), b.to_numpy(float), rtol=0, atol=1e-12, equal_nan=True):
                return False
        # An empty cell round-trips through CSV as NaN, so normalise before
        # comparing -- otherwise the check fires on its own serialisation and
        # a real difference would be indistinguishable from that noise.
        elif not a.fillna("").astype(str).equals(b.fillna("").astype(str)):
            return False
    return True


if __name__ == "__main__":
    raise SystemExit(main())
