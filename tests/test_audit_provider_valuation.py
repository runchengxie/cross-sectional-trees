import importlib
import json

import pandas as pd
import yaml
from market_data_platform.data_providers import _cache_tag, _fundamentals_cache_file


def _load_audit_module():
    return importlib.reload(
        importlib.import_module("cstree.research.hk_selected_provider_valuation_audit")
    )


def test_audit_provider_overlay_uses_cached_frames_without_provider_init(tmp_path):
    audit_module = _load_audit_module()
    run_dir = tmp_path / "runs" / "hk_sel_q_4way_g4_fixed_test"
    run_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = tmp_path / "cache" / "fundamentals" / "hk"
    cache_dir.mkdir(parents=True, exist_ok=True)
    report_path = tmp_path / "reports" / "audit.csv"

    data_cfg = {
        "provider": "rqdata",
        "start_date": "20200101",
        "end_date": "20200131",
        "cache_dir": str(tmp_path / "cache"),
    }
    overlay_cfg = {
        "enabled": True,
        "source": "provider",
        "provider": "rqdata",
        "endpoint": "get_factor",
        "fields": ["hk_total_market_val", "pe_ratio_ttm", "pb_ratio_ttm"],
        "column_map": {
            "trade_date": "trade_date",
            "symbol": "symbol",
            "market_cap": "hk_total_market_val",
            "pe_ttm": "pe_ratio_ttm",
            "pb": "pb_ratio_ttm",
        },
        "features": ["market_cap", "pe_ttm", "pb"],
    }
    config_used = {
        "market": "hk",
        "data": data_cfg,
        "fundamentals": {
            "enabled": True,
            "source": "file",
            "file": str(tmp_path / "fundamentals.parquet"),
            "provider_overlay": overlay_cfg,
        },
        "eval": {
            "sample_on_rebalance_dates": False,
        },
    }
    summary = {
        "eval": {"scored_file": str(run_dir / "eval_scored.parquet")},
        "fundamentals": {
            "provider_overlay": {
                "enabled": True,
                "cache_dir": str(cache_dir),
            }
        },
    }

    (run_dir / "config.used.yml").write_text(
        yaml.safe_dump(config_used, sort_keys=False),
        encoding="utf-8",
    )
    (run_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    eval_scored = pd.DataFrame(
        {
            "trade_date": ["2020-01-02", "2020-01-03"],
            "symbol": ["00001.HK", "00001.HK"],
            "score": [1.0, 0.8],
        }
    )
    eval_scored.to_parquet(run_dir / "eval_scored.parquet", index=False)

    cache_file = _fundamentals_cache_file(
        cache_dir,
        "hk",
        "rqdata",
        "00001.HK",
        "20200101",
        "20200131",
        _cache_tag(data_cfg),
        overlay_cfg,
    )
    pd.DataFrame(
        {
            "trade_date": ["2020-01-02", "2020-01-03"],
            "symbol": ["00001.HK", "00001.HK"],
            "market_cap": [100.0, 101.0],
            "pe_ttm": [10.0, 11.0],
            "pb": [1.0, 1.1],
            "valuation_trade_date": ["2020-01-02", "2020-01-03"],
        }
    ).to_parquet(cache_file, index=False)

    exit_code = audit_module.main(
        [
            "--run-dir",
            str(run_dir),
            "--out",
            str(report_path),
        ]
    )

    assert exit_code == 0
    report = pd.read_csv(report_path)
    assert report["valuation_coverage_pct"].tolist() == [100.0, 100.0]
    assert report["valuation_age_days_max"].tolist() == [0.0, 0.0]
