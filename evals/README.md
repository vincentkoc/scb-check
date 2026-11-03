# Clone quality evaluation

This fork tunes clone candidate selection, not the composite score weights.
`statement-bodies-v1` requires both three `SLOC` and two executable statements
in one language-configured body container. Names and literals remain normalized;
operators remain significant. Expression-bodied arrows and single-statement
wrappers are excluded. Separate branch arms do not contribute a combined count.

## Labelled regression suite

`clone_cases.json` contains 54 synthetic, manually labelled policy examples in
Python, JavaScript, TypeScript, Rust, C++, Zig, and Haskell. Each case provides
two or more files and exact expected clone spans and group membership. The suite includes real
two-statement clones, methods, async functions, generators, loops, nested
branches, wrappers, comments/docstrings, expression arrows, and operator changes.
The array-predicate regression is a reduced pattern from public
[`device-bootstrap-profile.ts`](https://github.com/openclaw/openclaw/blob/c67556df310f7cc50798ef51beac33a43714356a/src/shared/device-bootstrap-profile.ts).

The `tune` partition contains 16 minimal boundary cases. The `holdout` partition
contains 38 additional pattern and language controls. These are correlated,
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
upstream main `a8618228939def726c2ec48b354693e5aa1999d5`, and this fork's
`0.2.0+vk.1` analyzer, with the same frozen parser dependencies and evaluation
runner. Only the clone analyzer was substituted for the historical comparisons;
these are not full historical package benchmarks. The file records analyzer,
suite, dependency-lock, manifest, and parsed-symbol hashes.

| Analyzer | Cases passed | Labelled false positives | Labelled false negatives | Corpus clone SLOC |
| --- | ---: | ---: | ---: | ---: |
| Published `0.2.0` | 33/54 | 46 | 0 | 478 |
| Upstream `a861822` | 42/54 | 24 | 0 | 403 |
| Fork `0.2.0+vk.1` | 54/54 | 0 | 0 | 250 |

All three use the same 47 parsed files, 12,843 `SLOC`, and parsed-symbol digest.
Three existing TypeScript grammar failures remain visible:

- `src/agents/cli-runner.before-agent-reply-cron.test.ts`
- `src/infra/backup-create.ts`
- `extensions/codex/src/app-server/run-attempt-test-harness.ts`

Zero false positives here means zero against these labels. The corpus score
drop does not establish that every remaining clone is actionable. Engine
versions belong to separate scan baselines; do not interpret their score delta
as a source-code improvement.
