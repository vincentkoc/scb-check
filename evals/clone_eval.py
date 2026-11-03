"""Evaluate labelled clone cases or a hash-pinned external corpus."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Literal, TypedDict, cast

from scb_check import __version__
from scb_check.analysis.clones import detect_clones
from scb_check.tree_walking.artifacts import ProjectParseError
from scb_check.tree_walking.dispatch import ParsedFile
from scb_check.tree_walking.dispatch import parse_source_file


class SourceFile(TypedDict):
    """One synthetic source file."""

    path: str
    source: str


class CloneCase(TypedDict):
    """A manually labelled case, partitioned before tuning."""

    id: str
    split: Literal["tune", "holdout"]
    reason: str
    files: list[SourceFile]
    expected_groups: list[list[tuple[str, int, int]]]


class CloneSuite(TypedDict):
    """Versioned labelled suite."""

    schema: int
    policy: str
    cases: list[CloneCase]


class CorpusFile(TypedDict):
    """A content-pinned public corpus member."""

    path: str
    sha256: str
    scope: str


class Corpus(TypedDict):
    """Public source identity plus finite selection."""

    repository: str
    revision: str
    files: list[CorpusFile]


def evaluate_suite(suite_path: Path) -> dict[str, object]:
    """Report span precision/recall and exact group matches by split."""
    payload = suite_path.read_bytes()
    suite = cast("CloneSuite", json.loads(payload))
    if suite["schema"] != 1 or not suite["cases"]:
        raise ValueError("clone suite requires schema 1 and nonempty cases")
    if len({case["id"] for case in suite["cases"]}) != len(suite["cases"]):
        raise ValueError("clone suite case IDs must be unique")
    for split in ("tune", "holdout"):
        labels = {
            bool(case["expected_groups"])
            for case in suite["cases"]
            if case["split"] == split
        }
        if labels != {True, False}:
            raise ValueError(f"{split} requires positive and negative controls")
    totals: dict[str, Counter[str]] = {}
    failures = []
    for case in suite["cases"]:
        parsed = tuple(
            parse_source_file(Path(file["path"]), file["source"])
            for file in case["files"]
        )
        groups: dict[str, list[tuple[str, int, int]]] = {}
        for clone in detect_clones(parsed):
            groups.setdefault(clone.group_hash, []).append(
                (clone.file.as_posix(), clone.start_line, clone.end_line),
            )
        actual_groups = sorted(sorted(group) for group in groups.values())
        expected_groups = sorted(
            sorted(tuple(span) for span in group)
            for group in case["expected_groups"]
        )
        actual = Counter(span for group in actual_groups for span in group)
        expected = Counter(span for group in expected_groups for span in group)
        passed = actual_groups == expected_groups
        counts = totals.setdefault(case["split"], Counter())
        counts.update(
            cases=1,
            passed=int(passed),
            tp=sum((actual & expected).values()),
            fp=sum((actual - expected).values()),
            fn=sum((expected - actual).values()),
        )
        if not passed:
            failures.append(case["id"])
    return {
        "engine": __version__,
        "policy": suite["policy"],
        "suite_sha256": hashlib.sha256(payload).hexdigest(),
        "splits": {
            split: {
                **counts,
                "precision": _ratio(counts["tp"], counts["tp"] + counts["fp"]),
                "recall": _ratio(counts["tp"], counts["tp"] + counts["fn"]),
            }
            for split, counts in sorted(totals.items())
        },
        "failures": failures,
    }


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def evaluate_corpus(manifest_path: Path, checkout: Path) -> dict[str, object]:
    """Scan only hash-matching members; fail on missing or changing source."""
    payload = manifest_path.read_bytes()
    manifest = cast("Corpus", json.loads(payload))
    root = checkout.resolve()
    parsed: list[ParsedFile] = []
    parse_failures: list[str] = []
    for entry in manifest["files"]:
        source_path = (root / entry["path"]).resolve()
        if not source_path.is_relative_to(root):
            raise ValueError(f"corpus path escapes checkout: {entry['path']!r}")
        source = source_path.read_bytes()
        if hashlib.sha256(source).hexdigest() != entry["sha256"]:
            raise ValueError(f"corpus hash mismatch: {entry['path']!r}")
        try:
            parsed.append(
                parse_source_file(Path(entry["path"]), source.decode("utf-8")),
            )
        except ProjectParseError:
            parse_failures.append(entry["path"])
    clones = detect_clones(tuple(parsed))
    for entry in manifest["files"]:
        source = (root / entry["path"]).read_bytes()
        if hashlib.sha256(source).hexdigest() != entry["sha256"]:
            raise ValueError(f"corpus changed during scan: {entry['path']!r}")
    functions = [
        symbol.model_dump(mode="json")
        for file in parsed
        for symbol in file.module.symbols
    ]
    clone_lines = {
        (clone.file, line)
        for clone in clones
        for file in parsed
        if file.file == clone.file
        for line in file.module.sloc_lines
        if clone.start_line <= line <= clone.end_line
    }
    return {
        "engine": __version__,
        "repository": manifest["repository"],
        "revision": manifest["revision"],
        "manifest_sha256": hashlib.sha256(payload).hexdigest(),
        "requested_files": len(manifest["files"]),
        "files": len(parsed),
        "parse_failures": parse_failures,
        "sloc": sum(len(file.module.sloc_lines) for file in parsed),
        "symbol_sha256": hashlib.sha256(
            json.dumps(functions, sort_keys=True).encode(),
        ).hexdigest(),
        "clone_sloc": len(clone_lines),
        "clone_groups": len({clone.group_hash for clone in clones}),
        "clones": [
            {
                "path": clone.file.as_posix(),
                "start": clone.start_line,
                "end": clone.end_line,
                "group": clone.group_hash,
            }
            for clone in clones
        ],
    }


def main() -> None:
    """Print JSON evaluation evidence and fail on labelled mismatches."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--suite", type=Path, default=Path("evals/clone_cases.json")
    )
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--checkout", type=Path)
    args = parser.parse_args()
    result = evaluate_suite(args.suite)
    partial = False
    if args.manifest is not None:
        if args.checkout is None:
            parser.error("--manifest requires --checkout")
        corpus = evaluate_corpus(args.manifest, args.checkout)
        result["corpus"] = corpus
        partial = bool(corpus["parse_failures"])
    print(json.dumps(result, indent=2))  # noqa: T201
    raise SystemExit(2 if partial else int(bool(result["failures"])))


if __name__ == "__main__":
    main()
