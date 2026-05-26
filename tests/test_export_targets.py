import json
from pathlib import Path

import pandas as pd
import pytest

from cstree.liveops import export_targets


def _write_live_run(tmp_path: Path, *, sides: list[str] | None = None) -> Path:
    run_dir = tmp_path / "live_run"
    run_dir.mkdir()
    positions_path = run_dir / "positions_by_rebalance_live.csv"
    positions = pd.DataFrame(
        {
            "entry_date": ["2026-05-25", "2026-05-25"],
            "rebalance_date": ["2026-05-22", "2026-05-22"],
            "signal_asof": ["2026-05-22", "2026-05-22"],
            "symbol": ["00001.HK", "00700.HK"],
            "weight": [0.4, 0.6],
            "signal": [0.2, 0.1],
            "rank": [1, 2],
            "side": sides or ["long", "long"],
        }
    )
    positions.to_csv(positions_path, index=False)
    (run_dir / "summary.json").write_text(
        json.dumps(
            {
                "data": {"market": "hk", "provider": "rqdata", "end_date": "20260522"},
                "live": {"positions_file": str(positions_path)},
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "config.used.yml").write_text("market: hk\n", encoding="utf-8")
    return run_dir


def test_export_targets_emits_qexec_contract_and_lineage(tmp_path, monkeypatch, capsys):
    run_dir = _write_live_run(tmp_path)
    targets_path = tmp_path / "exports" / "targets.json"
    quality_calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        export_targets,
        "enforce_liveops_quality_gate",
        lambda **kwargs: quality_calls.append(kwargs),
    )

    export_targets.main(
        [
            "--run-dir",
            str(run_dir),
            "--as-of",
            "2026-05-26",
            "--target-source",
            "hk-monthly-live",
            "--target-gross-exposure",
            "0.8",
            "--fail-on-quality",
            "warning",
            "--out",
            str(targets_path),
        ]
    )

    output = capsys.readouterr().out
    lineage_path = targets_path.with_suffix(".json.lineage.json")
    assert str(targets_path) in output
    assert str(lineage_path) in output
    payload = json.loads(targets_path.read_text(encoding="utf-8"))
    assert payload == {
        "asof": "2026-05-26",
        "source": "hk-monthly-live",
        "target_gross_exposure": 0.8,
        "targets": [
            {"symbol": "1", "market": "HK", "target_weight": 0.4},
            {"symbol": "700", "market": "HK", "target_weight": 0.6},
        ],
    }

    lineage = json.loads(lineage_path.read_text(encoding="utf-8"))
    assert lineage["target_contract"] == "quant-execution-engine.targets/v2"
    assert lineage["selection"]["source"] == "live"
    assert lineage["selection"]["positions_file"].endswith("positions_by_rebalance_live.csv")
    assert lineage["selection"]["weight_sum"] == 1.0
    assert lineage["upstream_files"]["summary.json"].endswith("summary.json")
    assert quality_calls == [
        {
            "command_name": "export-targets",
            "run_dir": run_dir,
            "config_ref": None,
            "fail_on_quality": "warning",
        }
    ]


def test_export_targets_rejects_short_holdings(tmp_path, monkeypatch):
    run_dir = _write_live_run(tmp_path, sides=["long", "short"])
    monkeypatch.setattr(export_targets, "enforce_liveops_quality_gate", lambda **_kwargs: None)

    with pytest.raises(SystemExit, match="only supports long-only holdings"):
        export_targets.main(
            [
                "--run-dir",
                str(run_dir),
                "--as-of",
                "2026-05-26",
                "--out",
                str(tmp_path / "targets.json"),
            ]
        )


def test_export_targets_requires_explicit_run_or_config(tmp_path):
    with pytest.raises(SystemExit, match="requires --config or --run-dir"):
        export_targets.main(["--out", str(tmp_path / "targets.json")])
