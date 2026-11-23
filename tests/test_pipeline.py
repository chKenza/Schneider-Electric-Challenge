"""Step 12 – the one-command pipeline: every stage is a real module, in dependency order."""

from __future__ import annotations

import importlib.util

from src.pipeline import NAMES, STAGES


def test_every_stage_is_a_runnable_module():
    for name, _, cmd in STAGES:
        spec = importlib.util.find_spec(cmd[0])
        assert spec is not None, f"{name}: module {cmd[0]} not found"
        assert "__main__" in spec.loader.get_source(cmd[0]), f"{name}: {cmd[0]} has no command-line entry"


def test_stages_run_in_dependency_order():
    order = {n: i for i, n in enumerate(NAMES)}
    needs = {  # stage -> stages whose outputs it reads
        "features": ["data_prep", "external_data"],
        "baselines": ["data_prep"],
        "models": ["features", "baselines"],  # the combination is scored against the random walk
        "submission": ["models"],
    }
    for stage, before in needs.items():
        assert all(order[b] < order[stage] for b in before), stage
    assert NAMES[-1] == "submission"
