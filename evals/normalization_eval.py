"""Compare clone normalization experiments without changing the engine."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
from collections import defaultdict
from collections.abc import Callable
from collections.abc import Iterator
from contextlib import contextmanager
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Literal, TypedDict, cast
from unittest.mock import patch

from evals.clone_eval import CloneCase
from evals.clone_eval import Corpus
from evals.clone_eval import evaluate_corpus
from evals.clone_eval import evaluate_suite
from scb_check import __version__
from scb_check.analysis import clones
from scb_check.tree_walking.artifacts import ProjectParseError
from scb_check.tree_walking.models import Language

if TYPE_CHECKING:
    from tree_sitter import Node

Variant = Literal[
    "baseline",
    "regex-exact",
    "template-structure",
    "embedded-code",
    "exact-literals",
]
VARIANTS: tuple[Variant, ...] = (
    "baseline",
    "regex-exact",
    "template-structure",
    "embedded-code",
    "exact-literals",
)
type Normalizer = Callable[
    [Node, clones._NormalizeContext, dict[str, str]], str  # noqa: SLF001
]


class Family(TypedDict):
    """One source family confined to a single split."""

    split: Literal["tune", "holdout"]
    path: str
    sha256: str
    spans: list[list[int]]


class Origin(TypedDict):
    """The public corpus from which cases were derived."""

    repository: str
    revision: str
    manifest_sha256: str


class SourceCase(CloneCase):
    """A clone label plus separate source and usefulness information."""

    family: str
    usefulness: str


class SourceSuite(TypedDict):
    """Frozen source-derived labels and provenance."""

    schema: int
    policy: str
    source: Origin
    families: dict[str, Family]
    cases: list[SourceCase]


def digest(path: Path) -> str:
    """Hash exact input bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_source_suite(suite_path: Path, manifest_path: Path) -> None:
    """Reject source drift, missing families and family leakage across splits."""
    suite = cast("SourceSuite", json.loads(suite_path.read_bytes()))
    manifest = cast("Corpus", json.loads(manifest_path.read_bytes()))
    origin = suite["source"]
    if (
        origin["manifest_sha256"],
        origin["repository"],
        origin["revision"],
    ) != (digest(manifest_path), manifest["repository"], manifest["revision"]):
        raise ValueError("source suite does not match its corpus manifest")
    _validate_families(suite["families"], manifest)
    _validate_membership(suite["cases"], suite["families"])


def _validate_families(families: dict[str, Family], manifest: Corpus) -> None:
    pins = {entry["path"]: entry["sha256"] for entry in manifest["files"]}
    for family in families.values():
        if pins.get(family["path"]) != family["sha256"]:
            raise ValueError("source family does not match its pinned file")
        if not family["spans"] or any(
            len(span) != 2 or not 1 <= span[0] <= span[1]  # noqa: PLR2004
            for span in family["spans"]
        ):
            raise ValueError("source family requires valid original spans")


def _validate_membership(
    cases: list[SourceCase], families: dict[str, Family]
) -> None:
    if {case["family"] for case in cases} != set(families):
        raise ValueError("source suite has missing or unknown families")
    for case in cases:
        if families[case["family"]]["split"] != case["split"]:
            raise ValueError("source family crosses tune and holdout splits")
        if not case["usefulness"].strip():
            raise ValueError("source case requires a separate usefulness note")


def _literal_source(node: Node) -> str:
    return json.dumps([node.type, (node.text or b"").decode()])


def _template_structure(
    node: Node,
    context: clones._NormalizeContext,
    variable_map: dict[str, str],
    original: Normalizer,
) -> str:
    substitutions = [
        child
        for child in node.named_children
        if child.type == "template_substitution"
    ]
    if not substitutions:
        return original(node, context, variable_map)
    normalized = (
        clones._normalize_node(child, context, variable_map)  # noqa: SLF001
        for child in substitutions
    )
    return f"template_string({','.join(normalized)})"


def _normalize_candidate(
    node: Node,
    context: clones._NormalizeContext,
    variable_map: dict[str, str],
    *,
    variant: Variant,
    original: Normalizer,
) -> str:
    if variant == "exact-literals" and node.type in context.literal_node_types:
        return _literal_source(node)
    if context.language not in {Language.JAVASCRIPT, Language.TYPESCRIPT}:
        return original(node, context, variable_map)
    if node.type == "regex" and variant in {"regex-exact", "embedded-code"}:
        return _literal_source(node)
    if node.type == "template_string" and variant in {
        "template-structure",
        "embedded-code",
    }:
        return _template_structure(node, context, variable_map, original)
    return original(node, context, variable_map)


@contextmanager
def normalization_variant(variant: Variant) -> Iterator[None]:
    """Apply one serial, process-local experiment and always restore the engine."""
    if variant not in VARIANTS:
        raise ValueError(f"unknown normalization variant: {variant}")
    original = clones._normalize_node  # noqa: SLF001
    normalize = partial(
        _normalize_candidate, variant=variant, original=original
    )

    # The original recursion resolves this module hook too. Experiments must run
    # serially; the patch is never installed in the CLI or analysis package.
    with patch.object(clones, "_normalize_node", normalize):
        yield


def group_spans(corpus: dict[str, object]) -> list[list[tuple[str, int, int]]]:
    """Compare clone membership independently of changed structural hashes."""
    groups: dict[str, list[tuple[str, int, int]]] = defaultdict(list)
    for clone in cast("list[dict[str, str | int]]", corpus["clones"]):
        groups[str(clone["group"])].append(
            (str(clone["path"]), int(clone["start"]), int(clone["end"]))
        )
    return sorted(sorted(spans) for spans in groups.values())


def corpus_comparison(
    corpus: dict[str, object], baseline: dict[str, object]
) -> dict[str, object]:
    """Retain changed memberships and exact summary identity without duplicate rows."""
    groups = group_spans(corpus)
    before = group_spans(baseline)
    return {
        **{key: value for key, value in corpus.items() if key != "clones"},
        "group_spans_sha256": hashlib.sha256(
            json.dumps(groups).encode()
        ).hexdigest(),
        "removed_groups": [spans for spans in before if spans not in groups],
        "added_groups": [spans for spans in groups if spans not in before],
    }


def run_experiment(
    suite_path: Path,
    legacy_path: Path,
    manifest_path: Path,
    checkout: Path | None,
) -> dict[str, object]:
    """Report all outcomes; candidate-label mismatches are data, not CLI failures."""
    validate_source_suite(suite_path, manifest_path)
    inputs = (suite_path, legacy_path, manifest_path)
    hashes = [digest(path) for path in inputs]
    results: dict[str, dict[str, object]] = {}
    for variant in VARIANTS:
        with normalization_variant(variant):
            results[variant] = _evaluate_variant(
                suite_path, legacy_path, manifest_path, checkout
            )
    if checkout is not None:
        baseline = cast("dict[str, object]", results["baseline"]["corpus"])
        for result in results.values():
            corpus = cast("dict[str, object]", result["corpus"])
            result["corpus"] = corpus_comparison(corpus, baseline)
    if hashes != [digest(path) for path in inputs]:
        raise ValueError(
            "experiment labels or manifest changed during evaluation"
        )
    grammar = importlib.metadata.distribution("tree-sitter-typescript")
    return {
        "schema": 1,
        "kind": "eval-only-normalization-experiment",
        "engine": __version__,
        "python": platform.python_version(),
        "grammar": {
            "version": grammar.version,
            **json.loads(grammar.read_text("direct_url.json") or "{}"),
        },
        "dependency_lock_sha256": digest(Path("uv.lock")),
        "analyzer_sha256": digest(Path(clones.__file__)),
        "evaluator_sha256": digest(Path(__file__)),
        "label_evaluator_sha256": digest(
            Path(__file__).with_name("clone_eval.py")
        ),
        "variants": results,
    }


def _evaluate_variant(
    suite_path: Path,
    legacy_path: Path,
    manifest_path: Path,
    checkout: Path | None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "legacy": evaluate_suite(legacy_path),
        "source_derived": evaluate_suite(suite_path),
    }
    if checkout is not None:
        corpus = evaluate_corpus(manifest_path, checkout)
        if corpus["parse_failures"]:
            raise ValueError("experiment requires complete corpus parsing")
        result["corpus"] = corpus
    return result


def main() -> None:
    """Print an eval-only comparison; invalid or partial input exits two."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--suite", type=Path, default=Path("evals/source_derived_cases.json")
    )
    parser.add_argument(
        "--legacy-suite", type=Path, default=Path("evals/clone_cases.json")
    )
    parser.add_argument(
        "--manifest", type=Path, default=Path("evals/openclaw.json")
    )
    parser.add_argument("--checkout", type=Path)
    args = parser.parse_args()
    try:
        result = run_experiment(
            args.suite, args.legacy_suite, args.manifest, args.checkout
        )
    except (ValueError, OSError, ProjectParseError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2))  # noqa: T201


if __name__ == "__main__":
    main()
