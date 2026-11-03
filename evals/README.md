# Clone quality evaluation

This fork tunes clone candidate selection, not the composite score weights.
`statement-bodies-v1` requires both three `SLOC` and two executable statements
in one language-configured body container. Names and literals remain normalized;
operators remain significant. Expression-bodied arrows and single-statement
wrappers are excluded. Separate branch arms do not contribute a combined count.

## Labelled regression suite

`clone_cases.json` contains 60 synthetic, manually labelled policy examples in
Python, JavaScript, TypeScript, Rust, C++, Zig, and Haskell. Each case provides
two or more files and exact expected clone spans and group membership. The suite includes real
two-statement clones, methods, async functions, generators, loops, nested
branches, wrappers, comments/docstrings, expression arrows, and operator changes. Six
generic-await controls exercise call/member/subscript chains, non-null assertions,
parentheses, wrappers, concise arrows and distinct comparisons.
The array-predicate regression is a reduced pattern from public
[`device-bootstrap-profile.ts`](https://github.com/openclaw/openclaw/blob/c67556df310f7cc50798ef51beac33a43714356a/src/shared/device-bootstrap-profile.ts).

The `tune` partition contains 16 minimal boundary cases. The `holdout` partition
contains 44 additional pattern and language controls. These are correlated,
deliberately selected regressions, not an independent estimate of precision on
arbitrary software. A label says whether a syntax block satisfies this clone
policy; it does not say whether a developer should refactor it.

```sh
uv sync --frozen --python 3.13
uv run python -m evals.clone_eval
uv run pytest tests/analysis/test_clone_eval.py
```

The evaluator reports exact case matches and span-level true positives,
false positives, false negatives, precision, and recall by partition. Undefined
ratios are `null`. Any labelled mismatch exits `1`; parser/input errors must not
be treated as passing results.

## Public source corpus

`openclaw.json` pins 50 files (725,132 bytes) to public OpenClaw revision
[`c67556df`](https://github.com/openclaw/openclaw/commit/c67556df310f7cc50798ef51beac33a43714356a).
It includes 24 production-named files, 24 test-named files, and two extra
regression anchors. The manifest documents deterministic stratified selection
and records every file's SHA256. Filename classification includes developer/QA
helpers in production; this is not a representative whole-repository sample.
Source is not vendored and the evaluator never downloads or hydrates it.

```sh
uv run python -m evals.clone_eval \
  --manifest evals/openclaw.json --checkout /path/to/openclaw
```

Only manifest files are read. Their bytes must match before and after scanning;
the surrounding checkout can differ. Missing files, changed bytes, and escaped
paths fail. Parse failures are listed with requested/parsed file counts and exit
`2`. Reported corpus metrics cover parsed files only. They are observations,
not labelled precision or recall. Never improve a score by silently dropping a
file or rewriting application code to satisfy a grammar.

## Recorded comparison

[`results.json`](results.json) compares the published `0.2.0` clone analyzer,
upstream main `a8618228939def726c2ec48b354693e5aa1999d5`, and the
`0.2.0+vk.1` fork analyzer, with the same frozen parser dependencies and evaluation
runner. Only the clone analyzer was substituted for the historical comparisons;
these are not full historical package benchmarks. The file records analyzer,
suite, dependency-lock, manifest, and parsed-symbol hashes.

| Analyzer | Cases passed | Labelled false positives | Labelled false negatives | Corpus clone SLOC |
| --- | ---: | ---: | ---: | ---: |
| Published `0.2.0` | 33/54 | 46 | 0 | 478 |
| Upstream `a861822` | 42/54 | 24 | 0 | 403 |
| Fork `0.2.0+vk.1` | 54/54 | 0 | 0 | 250 |

Those historical measurements use the same 47 parsed files, 12,843 `SLOC`, and
parsed-symbol digest. Their frozen TypeScript grammar failed on:

- `src/agents/cli-runner.before-agent-reply-cron.test.ts`
- `src/infra/backup-create.ts`
- `extensions/codex/src/app-server/run-attempt-test-harness.ts`

Zero false positives here means zero against these labels. The corpus score
drop does not establish that every remaining clone is actionable. Engine
versions belong to separate scan baselines; do not interpret their score delta
as a source-code improvement.

## Native grammar coverage baseline

[`grammar_results.json`](grammar_results.json) records `0.2.0+vk.2` with the
native Git-pinned grammar fork, the exact dependency-lock hash, and the same
unchanged labelled suite and corpus manifest. All 54 cases pass with zero
labelled false positives or negatives. All 50 requested files parse: 14,845
`SLOC`, 282 clone `SLOC` and 23 clone groups.

On the original 47-file overlap, the function-symbol digest, 12,843 `SLOC`, 250
clone `SLOC` and 19 groups match the historical `vk.1` result. The full 50-file
values add previously unparsed source; this is a new coverage baseline, not
an application-code improvement or a measured precision gain.

The native regression set covers type-only wildcard exports, import member
type arguments, arrays, indexed/parenthesized types, invalid forms and ordinary
expression controls in TS and TSX. The scanner still supports `.ts`, not `.tsx`.
In that baseline, generic-await AST ownership was an inherited limitation,
recorded as expected-failure tests separately from passing syntax controls. No source
preprocessing or metric-weight changes are used.


## Await ownership baseline

[`await_results.json`](await_results.json) records `0.2.0+vk.3`, which pins the
repaired native grammar and adds six labelled holdout
controls. The clone policy and metric weights stay unchanged. These correlated
regressions do not establish independent precision; AST ownership is checked by
parser assertions and the native fork's compiler-reference suite, not clone labels.
Use a new baseline because corrected AST grouping can change structural hashes.

All 60 cases pass with zero labelled false positives or negatives. All 50 frozen
files parse. Their 14,845 `SLOC`, function-symbol digest, 282 clone `SLOC`, 23
groups, group spans and structural hashes match the previous coverage baseline.
The native compiler-reference suite improves valid AST matches from 45 to 92
of 100 vectors per dialect; eight valid gaps and one invalid-syntax gap remain
explicitly recorded there. Passing clone labels do not imply complete parser coverage.
