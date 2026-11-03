from __future__ import annotations

from pathlib import Path

import pytest

from evals.clone_eval import evaluate_suite
from scb_check.analysis.clones import detect_clones
from scb_check.tree_walking.dispatch import parse_source_file


@pytest.mark.parametrize("suffix", ["js", "ts"])
@pytest.mark.parametrize(
    ("left", "right", "matches"),
    [
        ('"one"', "`two`", True),
        ("`${value}`", "`prefix ${value} suffix`", True),
        ("`${value}${other}`", "`${value}: ${other}`", True),
        ("`${value + 1}`", "`${value + 2}`", True),
        ("`${value + 1}`", "`${value - 1}`", False),
        ("`${value}/${other}`", "`${other}/${value}`", False),
        ("`${value}/${other}`", "`${value}/${value}`", False),
        ("`${value.name}`", "`${value.name()}`", False),
        ("`${value ? other : value}`", "`${value && other}`", False),
        ("`${`${value}`}`", "`${`prefix ${value}`}`", True),
        ("`${`${value + 1}`}`", "`${`${value - 1}`}`", False),
        ("`${value /* note */ + 1}`", "`${value + 2}`", True),
        ("`plain`", "`${value}`", False),
        ("`${/a/.test(value)}`", "`${/b/i.test(value)}`", True),
        (r"`escaped \${value}`", '"ordinary data"', True),
    ],
)
def test_template_clone_structure(
    suffix: str, left: str, right: str, *, matches: bool
) -> None:
    """Preserve executable structure while normalizing static data and names."""
    sources = [
        f"function format(value, other) {{\n const message = {expression};\n return message;\n}}\n"
        for expression in (left, right)
    ]
    sources[1] = (
        sources[1]
        .replace("value", "entry")
        .replace("other", "next")
        .replace("message", "text")
    )
    parsed = tuple(
        parse_source_file(Path(f"{name}.{suffix}"), source)
        for name, source in zip(("left", "right"), sources, strict=True)
    )
    clones = detect_clones(parsed)
    assert len(clones) == (2 if matches else 0)
    assert all((clone.start_line, clone.end_line) == (1, 4) for clone in clones)


def test_production_source_cases_keep_only_regex_policy_differences() -> None:
    """Promote template structure without promoting the separate regex rule."""
    result = evaluate_suite(Path("evals/source_derived_cases.json"))
    assert result["failures"] == ["E1-patterns", "E3-flags", "R1-extractors"]
