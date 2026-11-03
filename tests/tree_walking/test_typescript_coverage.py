from __future__ import annotations

from pathlib import Path

import pytest
from tree_sitter import Tree

from scb_check.tree_walking.artifacts import ProjectParseError
from scb_check.tree_walking.dispatch import parse_source_file
from scb_check.tree_walking.models import Language


@pytest.mark.parametrize(
    "source",
    [
        'export type * from "./types";',
        'export type * as Types from "./types";',
        'let entries: import("node:fs").Dirent[];',
        'type Result = import("./types").Result<string>;',
        'type Results = import("./types").Result<string>[];',
        'const actual = await importOriginal<typeof import("./module")>();',
        'const actual = await vi.importActual<typeof import("./module")>("./module",);',
    ],
)
def test_valid_typescript_type_syntax(source: str) -> None:
    """Accept modern type syntax without changing source text or spans."""
    parsed = parse_source_file(Path("sample.ts"), source + "\n")
    assert parsed.source == source + "\n"
    assert parsed.module.language is Language.TYPESCRIPT
    assert parsed.module.sloc_lines == frozenset({1})


@pytest.mark.parametrize(
    "expression",
    [
        'await importOriginal<typeof import("./module")>()',
        'await vi.importActual<typeof import("./module")>("./module",)',
        "await load<Module>()",
    ],
)
def test_await_owns_the_complete_call(expression: str) -> None:
    """A successful parse must preserve await/call ownership."""
    parsed = parse_source_file(
        Path("sample.ts"), f"const value = {expression};"
    )
    assert isinstance(parsed.native_tree, Tree)
    declaration = parsed.native_tree.root_node.named_children[0].named_children[
        0
    ]
    value = declaration.child_by_field_name("value")
    assert value is not None
    assert value.type == "await_expression"
    assert value.named_children[0].type == "call_expression"


@pytest.mark.parametrize(
    "source",
    [
        "export type * from;",
        'type Broken = import("./types").;',
        'const actual = await read<typeof import("./module")>(;',
    ],
)
def test_invalid_typescript_remains_a_parse_failure(source: str) -> None:
    """Supporting valid type syntax must not make parsing fail open."""
    with pytest.raises(ProjectParseError, match="failed to parse"):
        parse_source_file(Path("broken.ts"), source)


def test_type_syntax_preserves_runtime_function_facts() -> None:
    """Types and import queries do not add runtime functions or decisions."""
    source = """async function load(enabled: boolean) {
  const actual = await vi.importActual<typeof import("./module")>("./module",);
  let entries: import("node:fs").Dirent[];
  if (enabled) return actual;
  return entries;
}
"""
    parsed = parse_source_file(Path("sample.ts"), source)
    assert parsed.source == source
    assert parsed.module.sloc_lines == frozenset({1, 2, 3, 4, 5})
    assert len(parsed.module.symbols) == 1
    function = parsed.module.symbols[0]
    assert function.name == "load"
    assert function.cyc_complexity == 2


@pytest.mark.parametrize(
    ("expression", "outer", "operand"),
    [
        ("await load<Module>()()", "await_expression", "call_expression"),
        ("await load<Module>().value", "await_expression", "member_expression"),
        (
            "await load<Module>()[index]",
            "await_expression",
            "subscript_expression",
        ),
        ("await load!<Module>()", "await_expression", "call_expression"),
        ("await load<Module>()!", "await_expression", "non_null_expression"),
        (
            "await load<Module>().value++",
            "await_expression",
            "update_expression",
        ),
        (
            "await new Factory<Module>()()",
            "await_expression",
            "call_expression",
        ),
        (
            "(await load)<Module>()",
            "call_expression",
            "parenthesized_expression",
        ),
        (
            "await load<Module>() < limit",
            "binary_expression",
            "await_expression",
        ),
        (
            "await load<Module> + value",
            "binary_expression",
            "binary_expression",
        ),
    ],
)
def test_await_chains_preserve_source_and_ownership(
    expression: str,
    outer: str,
    operand: str,
) -> None:
    """Keep postfix ownership and comparison boundaries in the native tree."""
    source = f"const value = {expression};"
    parsed = parse_source_file(Path("sample.ts"), source)
    assert parsed.source == source
    assert parsed.module.sloc_lines == frozenset({1})
    assert isinstance(parsed.native_tree, Tree)
    value = (
        parsed.native_tree.root_node.named_children[0]
        .named_children[0]
        .child_by_field_name("value")
    )
    assert value is not None
    assert value.type == outer
    assert value.named_children[0].type == operand
    assert value.text == expression.encode()
    if outer == "await_expression":
        assert (
            value.named_children[0].text
            == expression.removeprefix("await ").encode()
        )
