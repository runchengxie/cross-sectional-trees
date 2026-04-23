from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from cstree import pipeline
from cstree.data_interface import DataInterface


def _build_frames(
    symbols: list[str],
    dates: pd.DatetimeIndex,
    *,
    close_map: dict[str, np.ndarray] | None = None,
    vol_map: dict[str, np.ndarray] | None = None,
    include_amount: bool = True,
) -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    steps = np.arange(len(dates), dtype=float)
    close_map = close_map or {}
    vol_map = vol_map or {}
    for idx, symbol in enumerate(symbols):
        close = close_map.get(symbol)
        if close is None:
            close = 100.0 + steps + idx * 5.0
        vol = vol_map.get(symbol)
        if vol is None:
            vol = np.full(len(dates), 1000.0 + idx, dtype=float)
        payload = {
            "trade_date": [d.strftime("%Y%m%d") for d in dates],
            "symbol": symbol,
            "close": np.asarray(close, dtype=float),
            "vol": np.asarray(vol, dtype=float),
        }
        if include_amount:
            payload["amount"] = payload["close"] * payload["vol"]
        frames[symbol] = pd.DataFrame(payload)
    return frames


def _run_pipeline(tmp_path, monkeypatch, config, frames, basic_df=None) -> Path:
    def fake_init_client(self):
        self.client = None

    def fake_fetch_daily(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        return frames[symbol].copy()

    def fake_load_basic(self, symbols=None) -> pd.DataFrame:
        return basic_df.copy() if basic_df is not None else pd.DataFrame()

    monkeypatch.setattr(DataInterface, "_init_client", fake_init_client)
    monkeypatch.setattr(DataInterface, "fetch_daily", fake_fetch_daily)
    monkeypatch.setattr(DataInterface, "load_basic", fake_load_basic)

    config_path = tmp_path / "config.yml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    pipeline.run(str(config_path))

    output_dir = Path(config["eval"]["output_dir"])
    run_dirs = sorted(output_dir.glob(f"{config['eval']['run_name']}_*"))
    assert len(run_dirs) == 1
    return run_dirs[0]
