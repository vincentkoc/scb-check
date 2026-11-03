from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from evals.clone_eval import CloneCase
from evals.clone_eval import evaluate_corpus
from evals.clone_eval import evaluate_suite
from scb_check.analysis.clones import detect_clones
from scb_check.tree_walking.dispatch import parse_source_file

_CORPUS = json.loads(
    (Path(__file__).parents[2] / "evals" / "clone_cases.json").read_text(),
)


@pytest.mark.parametrize("case", _CORPUS["cases"], ids=lambda case: case["id"])
def test_labelled_clone_case(case: CloneCase) -> None:
    """Match complete labelled spans and independent clone groups."""
    parsed = tuple(
        parse_source_file(Path(file["path"]), file["source"])
        for file in case["files"]
    )
    clones = detect_clones(parsed)
    actual = sorted(
        sorted(
            (clone.file.as_posix(), clone.start_line, clone.end_line)
            for clone in clones
            if clone.group_hash == group
        )
        for group in {clone.group_hash for clone in clones}
    )
    expected = sorted(
        sorted(tuple(span) for span in group)
        for group in case["expected_groups"]
    )
    assert actual == expected, case["reason"]


def test_eval_reports_missed_labels(tmp_path: Path) -> None:
    """An incorrect end span fails even when its clone start matches."""
    suite = tmp_path / "suite.json"
    corpus = json.loads(json.dumps(_CORPUS))
    corpus["cases"][0]["expected_groups"][0][0][2] = 999
    suite.write_text(json.dumps(corpus))
    result = evaluate_suite(suite)
    assert result["failures"] == ["js-two-statements"]


def test_eval_rejects_wrong_groups(tmp_path: Path) -> None:
    """Matching spans cannot hide incorrectly merged clone families."""
    corpus = json.loads(json.dumps(_CORPUS))
    case = next(
        case
        for case in corpus["cases"]
        if case["id"] == "ts-independent-groups"
    )
    case["expected_groups"] = [
        [span for group in case["expected_groups"] for span in group]
    ]
    suite = tmp_path / "suite.json"
    suite.write_text(json.dumps(corpus))
    assert evaluate_suite(suite)["failures"] == ["ts-independent-groups"]


@pytest.mark.parametrize(
    "selection", ["empty", "positive", "negative", "duplicate"]
)
def test_eval_rejects_lost_controls(tmp_path: Path, selection: str) -> None:
    """Truncated or duplicate suites cannot manufacture a green result."""
    corpus = json.loads(json.dumps(_CORPUS))
    if selection == "empty":
        corpus["cases"] = []
    elif selection == "duplicate":
        corpus["cases"].append(corpus["cases"][0])
    else:
        corpus["cases"] = [
            case
            for case in corpus["cases"]
            if bool(case["expected_groups"]) == (selection == "positive")
        ]
    suite = tmp_path / "suite.json"
    suite.write_text(json.dumps(corpus))
    with pytest.raises(
        ValueError, match=r"(clone suite|requires positive and negative)"
    ):
        evaluate_suite(suite)


def test_external_corpus_preserves_parse_failures(tmp_path: Path) -> None:
    """Unparseable pinned source remains visible as partial coverage."""
    source = b"const broken = ;\n"
    (tmp_path / "broken.ts").write_bytes(source)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "repository": "https://example.com/project",
                "revision": "fixture",
                "files": [
                    {
                        "path": "broken.ts",
                        "scope": "tests",
                        "sha256": hashlib.sha256(source).hexdigest(),
                    }
                ],
            }
        )
    )
    result = evaluate_corpus(manifest, tmp_path)
    assert result["requested_files"] == 1
    assert result["files"] == 0
    assert result["parse_failures"] == ["broken.ts"]
    assert result["sloc"] == 0


@pytest.mark.parametrize("path", ["file.ts", "../outside.ts"])
def test_external_corpus_rejects_wrong_inputs(
    tmp_path: Path, path: str
) -> None:
    """Changed bytes and paths outside the selected checkout fail closed."""
    (tmp_path / "file.ts").write_text("const changed = true;\n")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "repository": "https://example.com/project",
                "revision": "fixture",
                "files": [{"path": path, "scope": "tests", "sha256": "0" * 64}],
            }
        )
    )
    with pytest.raises(
        ValueError, match=r"corpus (hash mismatch|path escapes)"
    ):
        evaluate_corpus(manifest, tmp_path)
