import types

import pandas as pd
import pytest

from csxgb.project_tools import verify_tushare_tokens as verify


def test_load_local_env_reads_first_existing_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TUSHARE_TOKEN", raising=False)

    env_path = tmp_path / ".env"
    env_path.write_text("TUSHARE_TOKEN=from_env_file\n# comment\n", encoding="utf-8")

    verify.load_local_env()
    assert verify.os.getenv("TUSHARE_TOKEN") == "from_env_file"


def test_resolve_env_keys_falls_back_to_legacy(monkeypatch):
    monkeypatch.delenv("TUSHARE_TOKEN", raising=False)
    monkeypatch.delenv("TUSHARE_TOKEN_2", raising=False)
    monkeypatch.setenv("TUSHARE_API_KEY", "legacy-token")

    assert verify.resolve_env_keys() == ["TUSHARE_API_KEY"]


def test_check_token_returns_missing_error(monkeypatch):
    monkeypatch.delenv("TUSHARE_TOKEN", raising=False)
    result = verify.check_token("TUSHARE_TOKEN")
    assert result["ok"] is False
    assert "未设置" in result["message"]


def test_check_token_success(monkeypatch):
    monkeypatch.setenv("TUSHARE_TOKEN", "token-ok")

    class _FakePro:
        def user(self, token):
            assert token == "token-ok"
            return pd.DataFrame([{"user_id": "u1", "points": 100}])

    fake_ts = types.SimpleNamespace(pro_api=lambda token: _FakePro())
    monkeypatch.setattr(verify, "ts", fake_ts)

    result = verify.check_token("TUSHARE_TOKEN")
    assert result["ok"] is True
    assert result["user_id"] == "u1"
    assert result["has_rows"] is True


def test_check_token_handles_api_error(monkeypatch):
    monkeypatch.setenv("TUSHARE_TOKEN", "token-bad")

    def _raise(_token):
        raise RuntimeError("boom")

    fake_ts = types.SimpleNamespace(pro_api=_raise)
    monkeypatch.setattr(verify, "ts", fake_ts)

    result = verify.check_token("TUSHARE_TOKEN")
    assert result["ok"] is False
    assert "调用 TuShare 接口失败" in result["message"]


def test_main_exits_when_no_valid_token(monkeypatch):
    monkeypatch.setattr(verify, "load_local_env", lambda: None)
    monkeypatch.setattr(
        verify,
        "resolve_env_keys",
        lambda: ["TUSHARE_TOKEN", "TUSHARE_TOKEN_2"],
    )
    monkeypatch.setattr(
        verify,
        "check_token",
        lambda key: {"env_key": key, "ok": False, "message": "invalid"},
    )

    with pytest.raises(SystemExit, match="未检测到有效的 TuShare Token。"):
        verify.main([])
