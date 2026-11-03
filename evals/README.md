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

## Source-derived normalization experiment

`source_derived_cases.json` freezes 16 additional cases before running candidate
normalizers: eight tune cases from the elicitation and matrix-cache families,
and eight holdout cases from the relay-extraction and wizard-guard families.
Every derivative stays with its source family. Four cases are exact source
excerpts; the others are explicitly described transformations. File hashes,
revision and original spans refer to the existing public corpus. The derived
excerpts retain the [OpenClaw MIT notice](LICENSE.openclaw).

The candidate label policy preserves regex source (including flags) and template
substitution structure, while normalizing ordinary data and consistent names.
It retains the three-`SLOC`, two-statement minimum. These labels describe this
proposed structural match rule, not the current production policy. Static
template text and numeric/string data inside substitutions remain normalized.
Regex-equivalent spellings and flag-order equivalence are outside this rule;
`new RegExp` strings and tagged-template DSL semantics are not interpreted.

Each case separately records refactoring usefulness. In particular, stricter
regex matching separates the relay-ID and generation extractors even though a
shared extraction helper may be worthwhile. A candidate-policy match rate is
not a measure of actionable-refactoring precision. The corpus and families were
selected after inspecting existing findings, so this is a correlated regression
experiment, not blind validation or an estimate for arbitrary software.

Labels were independently reviewed and frozen in signed commit
[`4fda778`](https://github.com/vincentkoc/scb-check/commit/4fda77870a3c25a87daf391736b18039cbce128c)
before candidate implementation or detector runs. The experiment additionally
tests plain templates versus quoted strings and the presence of static template
text; those implementation regressions do not enlarge the frozen 16-case suite.

```sh
uv run python -m evals.normalization_eval
uv run python -m evals.normalization_eval --checkout /path/to/openclaw
uv run pytest tests/analysis/test_normalization_eval.py
```

The runner temporarily replaces the normalizer in its own process, restores it
after normal/error paths, and runs variants serially. It never changes installed
package files or the production CLI. Candidate-label mismatches are reported as
data, so a completed comparison exits `0`; source/manifest errors and partial
corpus parsing exit `2`. External source bytes must match the pinned manifest.
The runner never downloads source. Without `--checkout`, it evaluates labels
only. CI runs that mode; recorded corpus results require the external bytes.

[`normalization_results.json`](normalization_results.json) records the `vk.3`
experiment's exact analyzer, evaluator, lock, suites and manifest identities with Python 3.13.13 and
the pinned native grammar. All variants parse all 50 files, retain 14,845 `SLOC`
and the same function-symbol digest. Clone groups are compared by member spans,
independently of changed structural hashes.

| Experimental normalizer | Existing cases | Candidate-policy cases | Corpus clone SLOC / groups |
| --- | ---: | ---: | ---: |
| Production baseline | 60/60 | 11/16 | 282 / 23 |
| Exact regex source | 60/60 | 14/16 | 264 / 21 |
| Template expression structure | 60/60 | 13/16 | 276 / 22 |
| Both executable-literal rules | 60/60 | 16/16 | 258 / 20 |
| Every literal exact | 49/60 | 10/16 | 108 / 14 |

The combined rule has 18 matching labelled spans and no candidate-policy false
positives or negatives on these 16 cases. Making every literal exact loses 22
labelled spans in the existing suite and 12 in the source-derived suite. A lower
corpus clone count alone would therefore select an overstrict detector.

The `vk.3` experiment did not itself change production. Template-expression
structure is promoted separately in `vk.4`: it preserves operators and binding order
that the `vk.3` baseline discarded. Regex matching still needs a deliberate policy
decision: its two removed corpus groups include both short domain predicates and
the potentially useful shared relay-extraction algorithm. The additional group
removed by template matching is a test callback that logs a dynamic event ID
versus a constant message. None of these deltas measures application improvement.

## Production template baseline

`0.2.0+vk.4` combines the existing `statement-bodies-v1` body selection with
`template-structure-v1` normalization. Ordered substitutions share the enclosing
identifier map; comments and ordinary data normalize, including static template
text. Plain templates retain ordinary string matching. Regex matching stays as
in `vk.3`; the three regex-policy differences in the frozen source suite remain
explicit rather than relabelled.

[`template_results.json`](template_results.json) records the new production
identity separately from the immutable `vk.3` experiment. Use a new scan baseline;
changed structural hashes and clone counts do not imply improved application code.
The production run retains all 60 existing cases and matches 13 of the 16
source-derived labels. All 50 corpus files parse with unchanged SLOC and function
symbols; clone SLOC is 276 across 22 groups, matching the qualified template-only
experiment.
