import importlib
import sys

import pytest


def test_pipeline_data_compat_shim_warns_and_reexports_helpers():
    sys.modules.pop("cstree.pipeline.data", None)

    with pytest.warns(DeprecationWarning, match="cstree.pipeline.data is deprecated"):
        module = importlib.import_module("cstree.pipeline.data")

    assert module.__all__ == ["_load_research_panel", "_prepare_feature_dataset"]
    assert callable(module._load_research_panel)
    assert callable(module._prepare_feature_dataset)
