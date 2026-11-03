from __future__ import annotations

import json
from contextlib import nullcontext
from pathlib import Path
from typing import cast

import pytest

from evals import normalization_eval
from evals.clone_eval import evaluate_suite
from evals.normalization_eval import normalization_variant
from evals.normalization_eval import validate_source_suite
from scb_check.analysis.clones import detect_clones
from scb_check.tree_walking.dispatch import parse_source_file

SUITE = Path("evals/source_derived_cases.json")
MANIFEST = Path("evals/openclaw.json")


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ('"plain"', "`other text`"),
        ("`${value}`", "`prefix ${value} suffix`"),
        ("`${value}${value}`", "`${value}: ${value}`"),
    ],
)
def test_template_static_text_keeps_data_clones(left: str, right: str) -> None:
    """Template text presence and quote style are data, not executable structure."""
    parsed = tuple(
        parse_source_file(
            Path(name),
            f"function format(value) {{\n const text = {expression};\n return text;\n}}\n",
        )
        for name, expression in (("left.ts", left), ("right.ts", right))
    )
    with normalization_variant("template-structure"):
        assert len(detect_clones(parsed)) == 2


def test_embedded_code_matches_frozen_source_labels() -> None:
    """Preserve programs without losing ordinary data/rename clone controls."""
    validate_source_suite(SUITE, MANIFEST)
    with normalization_variant("embedded-code"):
        result = evaluate_suite(SUITE)
    assert result["failures"] == []


def test_exact_literals_lose_source_derived_data_clones() -> None:
    """A lower finding count cannot hide lost labelled positive controls."""
    with normalization_variant("exact-literals"):
        result = evaluate_suite(SUITE)
    assert {
        "E4-data",
        "M2-capacities",
        "M4-key-text",
        "R2-error-prose",
        "R3-expression-data",
        "W2-message-data",
    }.issubset(
        cast("list[str]", result["failures"]),
    )


@pytest.mark.parametrize("fail", [False, True])
def test_normalizer_restores_engine_behavior(fail: bool) -> None:  # noqa: FBT001
    """One experiment cannot change results of later baseline evaluations."""
    before = evaluate_suite(SUITE)
    expected = (
        pytest.raises(ValueError, match="deliberate evaluation failure")
        if fail
        else nullcontext()
    )
    with expected, normalization_variant("embedded-code"):
        assert evaluate_suite(SUITE)["failures"] == []
        if fail:
            raise ValueError("deliberate evaluation failure")
    assert evaluate_suite(SUITE) == before


@pytest.mark.parametrize(
    "mutation",
    ["split", "unknown", "missing", "pin", "manifest", "spans", "usefulness"],
)
def test_source_suite_rejects_unqualified_labels(
    tmp_path: Path, mutation: str
) -> None:
    """Family leakage and source/protocol drift must fail before evaluation."""
    suite = json.loads(SUITE.read_text())
    if mutation == "split":
        suite["cases"][0]["split"] = "holdout"
    elif mutation == "unknown":
        suite["cases"][0]["family"] = "unknown"
    elif mutation == "missing":
        suite["cases"] = [
            case for case in suite["cases"] if case["family"] != "matrix"
        ]
    elif mutation == "pin":
        suite["families"]["matrix"]["sha256"] = "0" * 64
    elif mutation == "manifest":
        suite["source"]["manifest_sha256"] = "0" * 64
    elif mutation == "spans":
        suite["families"]["matrix"]["spans"] = [[4, 1]]
    else:
        suite["cases"][0]["usefulness"] = " "
    path = tmp_path / "suite.json"
    path.write_text(json.dumps(suite))
    with pytest.raises(ValueError, match="source"):
        validate_source_suite(path, MANIFEST)


def test_experiment_rejects_partial_corpus(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing parser coverage cannot become a successful experiment."""
    monkeypatch.setattr(
        normalization_eval,
        "evaluate_corpus",
        lambda *_: {"parse_failures": ["broken.ts"]},
    )
    with pytest.raises(ValueError, match="complete corpus parsing"):
        normalization_eval.run_experiment(
            SUITE, Path("evals/clone_cases.json"), MANIFEST, Path("unused")
        )


def test_cli_parse_error_exits_two(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Malformed labelled source fails the command and restores the engine."""
    before = evaluate_suite(SUITE)
    suite = json.loads(SUITE.read_text())
    suite["cases"][0]["files"][0]["source"] = "function broken( {"
    path = tmp_path / "suite.json"
    path.write_text(json.dumps(suite))
    monkeypatch.setattr(
        "sys.argv", ["normalization_eval", "--suite", str(path)]
    )
    with pytest.raises(SystemExit, match="2") as error:
        normalization_eval.main()
    assert error.value.code == 2
    assert evaluate_suite(SUITE) == before
