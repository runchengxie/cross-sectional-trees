from collections.abc import Mapping

from cstree.pipeline.output_context import OutputContext, build_output_context


def _context(**overrides):
    fields = {
        "loaded": {"run_dir": "initial", "market": "hk"},
        "universe_inputs": {"symbols": ["00005.HK"]},
        "date_label_settings": {"TARGET": "ret_fwd"},
        "eval_settings": {"TOP_K": 10},
        "universe_filters": {"DROP_ST": True},
        "runtime_settings": {"SAVE_ARTIFACTS": True, "run_dir": "runtime"},
        "run_artifacts": {"run_dir": "artifact"},
        "panel_state": {"df": "panel"},
        "dataset_state": {"dataset": "features"},
        "split_state": {"train_df": "train"},
        "extras": {"run_dir": "final", "provider": "rqdata"},
    }
    fields.update(overrides)
    return build_output_context(**fields)


def test_output_context_keeps_mapping_contract():
    context = _context()

    assert isinstance(context, OutputContext)
    assert isinstance(context, Mapping)
    assert context["provider"] == "rqdata"
    assert context["symbols"] == ["00005.HK"]
    assert set(context) >= {"TARGET", "TOP_K", "SAVE_ARTIFACTS"}


def test_output_context_preserves_existing_override_order():
    context = _context()

    assert context["run_dir"] == "final"


def test_output_context_as_dict_returns_copy():
    context = _context()
    flat = context.as_dict()
    flat["provider"] = "changed"

    assert context["provider"] == "rqdata"
