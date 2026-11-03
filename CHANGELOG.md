# Changelog

All notable user-facing changes to `scb-check` are documented here.

## [0.2.0+vk.3] - 2026-11-03

### Fixed

- Pin the native grammar that keeps generic calls and postfix chains inside
  await expressions while preserving comparisons, constructors and parentheses.
- Promote the three generic-await ownership regressions to passing assertions.

### Added

- Six labelled TypeScript generic-await clone controls, expanding the regression
  suite to 60 cases without changing clone thresholds or score weights.
- Source-span and chain-ownership checks through the analysis engine. Grammar
  changes require a fresh measurement baseline; remaining native gaps stay
  documented in the grammar fork.

## [0.2.0+vk.2] - 2026-11-03

### Fixed

- Pin a native TypeScript grammar fork that accepts type-only wildcard exports,
  import member type arguments, and array, indexed and parenthesized import
  types. Application source is not rewritten.
- Parse all 50 files in the frozen public corpus; keep the 54 labelled clone
  cases unchanged. Changed coverage requires a new scan baseline.

### Added

- Syntax, source-span, invalid-input and runtime-function regressions, plus
  explicit expected failures for the inherited generic-await AST ownership gap.
- Git-pinned grammar provenance and source-build requirements. The uv lock is
  authoritative; requirements exports pin versions and Git revisions without
  hashes because pip cannot hash Git source requirements. Registry publishing
  remains restricted to the upstream repository.

## [0.2.0+vk.1] - 2026-11-03

### Fixed

- Restrict clone statement counts to language-configured body containers so
  arrow expression operands cannot become multi-statement clones.
- Require at least three `SLOC` independently of the two-statement threshold.

### Added

- A versioned clone quality suite with 54 labelled cases across seven languages,
  explicit tuning/holdout partitions, and a 50-file content-pinned public
  OpenClaw corpus. External corpus parse failures remain visible and exit `2`.
- Fork version `0.2.0+vk.1` to keep changed scores separate from upstream `0.2.0`.

## [0.2.0] - 2026-05-19

This release summarizes changes since `v0.1.0`.

### Added

- Added multi-language source discovery and tree walking for Python, Rust,
  JavaScript, TypeScript, Zig, Haskell, and C++ source files.
- Added structural rule findings to verbosity scoring, starting with
  `trivial-wrapper` for removable Python pass-through functions.
- Added `--output-format json` and kept `--report` as a JSON shortcut.
- Added duplicate-focused output and `--min-duplicate-lines` filtering.
- Added JSON report fields for `structural_rule_loc`,
  `structural_rule_findings`, `syntax_tree_count`, `syntax_node_count`, and
  `syntax_by_language`.
- Added packaged `ast-grep-cli` fallback behavior when a global `sg` executable
  is missing or fails.
- Added maintainer documentation for architecture, tree walking, and development
  workflow.

### Changed

- Expanded directory walking from Python-only files to supported source files
  across the configured language set.
- Updated `--include-all` to include gitignored files along with ignored,
  lower-severity, and boundary-suppressed findings.
- Reworked tree walking into language-specific Tree-sitter adapters that emit
  shared module IR and semantic project context.
- Included structural rule lines in the verbosity union alongside clone and
  ast-grep lines.
- Updated source directives so Python `scbc ignore[...]` comments can suppress
  ast-grep and structural rule findings.
- Replaced the old mental-model notes with focused maintainer guides under
  `docs/`.

### Fixed

- Narrowed `trivial-wrapper` detection to avoid flagging functions that should
  be kept, including decorated functions, dunder methods, inherited API
  implementations, constant returns, and wrappers around external calls.
- Preserved the `scb-check check` exit-code contract for findings, clean runs,
  and usage errors across the expanded reporting paths.

## [0.1.0] - 2026-04-24

### Added

- Initial release of `scb-check` as a Python CLI for reporting verbosity,
  erosion, and cognitive erosion metrics.
- Added clone detection, bundled Python ast-grep slop rules, source directives,
  JSON reporting, configuration discovery, and hash-checked dependency locks.

[0.2.0]: https://github.com/gabeorlanski/scb-check/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/gabeorlanski/scb-check/releases/tag/v0.1.0
