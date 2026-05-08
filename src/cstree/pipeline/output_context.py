from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class OutputContext(Mapping[str, Any]):
    loaded: Mapping[str, Any]
    universe_inputs: Mapping[str, Any]
    date_label_settings: Mapping[str, Any]
    eval_settings: Mapping[str, Any]
    universe_filters: Mapping[str, Any]
    runtime_settings: Mapping[str, Any]
    run_artifacts: Mapping[str, Any]
    panel_state: Mapping[str, Any]
    dataset_state: Mapping[str, Any]
    split_state: Mapping[str, Any]
    extras: Mapping[str, Any]
    _flat: dict[str, Any] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        flat: dict[str, Any] = {}
        for source in self.sources:
            flat.update(source)
        object.__setattr__(self, "_flat", flat)

    @property
    def sources(self) -> tuple[Mapping[str, Any], ...]:
        return (
            self.loaded,
            self.universe_inputs,
            self.date_label_settings,
            self.eval_settings,
            self.universe_filters,
            self.runtime_settings,
            self.run_artifacts,
            self.panel_state,
            self.dataset_state,
            self.split_state,
            self.extras,
        )

    def __getitem__(self, key: str) -> Any:
        return self._flat[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._flat)

    def __len__(self) -> int:
        return len(self._flat)

    def as_dict(self) -> dict[str, Any]:
        return dict(self._flat)


def build_output_context(
    *,
    loaded: Mapping[str, Any],
    universe_inputs: Mapping[str, Any],
    date_label_settings: Mapping[str, Any],
    eval_settings: Mapping[str, Any],
    universe_filters: Mapping[str, Any],
    runtime_settings: Mapping[str, Any],
    run_artifacts: Mapping[str, Any],
    panel_state: Mapping[str, Any],
    dataset_state: Mapping[str, Any],
    split_state: Mapping[str, Any],
    extras: Mapping[str, Any],
) -> OutputContext:
    return OutputContext(
        loaded=loaded,
        universe_inputs=universe_inputs,
        date_label_settings=date_label_settings,
        eval_settings=eval_settings,
        universe_filters=universe_filters,
        runtime_settings=runtime_settings,
        run_artifacts=run_artifacts,
        panel_state=panel_state,
        dataset_state=dataset_state,
        split_state=split_state,
        extras=extras,
    )
