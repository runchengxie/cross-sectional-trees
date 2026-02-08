import pytest

from csxgb.execution import (
    BpsCostModel,
    ExitPolicy,
    NoCostModel,
    build_cost_model,
    build_execution_model,
    build_exit_policy,
)


@pytest.mark.parametrize("value", ["none", "off", "zero"])
def test_build_cost_model_string_aliases_disable_cost(value):
    model = build_cost_model(value, default_bps=15.0)
    assert isinstance(model, NoCostModel)


@pytest.mark.parametrize("name", ["bps", "bp", "basis"])
def test_build_cost_model_mapping_aliases(name):
    model = build_cost_model({"name": name, "bps": 12, "round_trip": False}, default_bps=15.0)
    assert isinstance(model, BpsCostModel)
    assert model.bps == 12.0
    assert model.round_trip is False


def test_build_cost_model_unsupported_raises():
    with pytest.raises(ValueError, match="Unsupported cost model: flat"):
        build_cost_model({"name": "flat"}, default_bps=15.0)


def test_build_exit_policy_supports_alias_keys():
    policy = build_exit_policy(
        {"price_policy": "delay", "fallback_policy": "none"},
        default_price="strict",
        default_fallback="ffill",
    )
    assert isinstance(policy, ExitPolicy)
    assert policy.price_policy == "delay"
    assert policy.fallback_policy == "none"


def test_build_exit_policy_invalid_value_raises():
    with pytest.raises(ValueError, match="exit_policy.price must be one of: strict, ffill, delay."):
        build_exit_policy({"price": "bad"}, default_price="strict", default_fallback="ffill")


def test_build_execution_model_supports_cost_and_exit_alias():
    model = build_execution_model(
        {
            "cost": {"name": "bp", "bps": 8, "round_trip": False},
            "exit": {"price": "delay", "fallback": "none"},
        },
        default_cost_bps=20.0,
        default_exit_price_policy="strict",
        default_exit_fallback_policy="ffill",
    )
    assert isinstance(model.cost_model, BpsCostModel)
    assert model.cost_model.bps == 8.0
    assert model.cost_model.round_trip is False
    assert model.exit_policy.price_policy == "delay"
    assert model.exit_policy.fallback_policy == "none"


def test_build_execution_model_uses_defaults_when_empty():
    model = build_execution_model(
        None,
        default_cost_bps=20.0,
        default_exit_price_policy="ffill",
        default_exit_fallback_policy="ffill",
    )
    assert isinstance(model.cost_model, BpsCostModel)
    assert model.cost_model.bps == 20.0
    assert model.exit_policy.price_policy == "ffill"
    assert model.exit_policy.fallback_policy == "ffill"
