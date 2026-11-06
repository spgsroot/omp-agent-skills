---
name: eng-gates
description: Deterministic quality gates for Rust, Python and JS/TS - format, lint, types, tests, module boundaries, CRAP, duplication, mutation, benchmarks, plus guards against weakening the gates. Use when the user asks for full checks ("все проверки", "gate full", production-grade), when gates already exist in the repo and one fails, or when setting gates up in a repo (init, doctor). NOT an always-on step - the repo's own check command is the default after a code change.
---

# eng-gates

Gates decide when code is done — **when they are on**. When they are, a task
is finished only when `gate full` passes. Turning them on is the user's call
(see the strictness signal map), not yours.

Runner: `python3 tools/eng-gates/gate.py` inside a repo that ran `init`, otherwise
`python3 <this skill>/scripts/gate.py`. Add `-C <dir>` to point at another project.
Windows: `python3` is the Microsoft Store stub - substitute `python` (or `uv run python`) everywhere below;
the ub checks (`ub.crap`, `ub.dry`, `ub.mutate`) are unavailable there and report as a missing tool.

## Loop (when the user picked gates for this task)

1. Make one small change (one test, one function, one refactor step).
2. `gate.py fast` - seconds. Format, lint, types, tests, module boundaries, both guards. Changed files only.
3. Red: fix the first failure, rerun. Do not start the next unit while fast is red.
4. Unit done → commit (why, what, how it was proven).
5. Before saying "done" for a gates task, before review, before push: `gate.py full` - adds dependency audit, unused deps,
   CRAP, duplication, mutation, benchmarks, bundle size.
6. Report: paste the final summary line of `gate full`, and list every `WARN guard.suppress` entry.

Output: one line per check, then the tail of each failure. The full report is in `.gates/last.json`;
read it instead of rerunning. `--json` prints it. `--only rust,guard` runs a subset. `--all` checks the whole tree.

## Fixing failures - what is and is not allowed

| Failure | Fix | Never |
|---|---|---|
| `rust.clippy`, `py.lint`, `ts.lint` | change the code the lint names | `#[allow]`, `# noqa`, `eslint-disable` without `gate-allow: <reason>` |
| `*.types` | model the type properly, parse at the boundary | `as any`, `# type: ignore`, `@ts-ignore`, casts to silence |
| `*.test` | fix the code, or the test if the test is wrong about the requirement | loosen assertions, delete cases, skip, mock the unit under test |
| `py.imports`, `ts.deps` | move code to the right layer, introduce a port (trait / protocol / interface) in the lower layer | import across the boundary "just this once" |
| `ub.crap` | split the function, or test its branches, or both | delete branches you have not proven dead |
| `ub.dry` | extract the shared shape once it is the same decision | merge code that only looks alike but changes for different reasons |
| `ub.mutate` | add an assertion that kills the survivor; delete code no test can reach | assert on implementation details |
| `*.bench` | find the cause with a profiler, fix it, show the new number | change the baseline or the budget |
| `rust.deny`, `py.deps`, `ts.knip`, `rust.machete` | remove or replace the dependency, delete dead exports | add ignores |
| `guard.config` | revert your edit to the protected file | run `gate.py approve` (humans only) |
| `guard.suppress` | remove the suppression; if it is truly right, add `gate-allow: <reason>` on that line | hide it with a broader suppression |

If a rule itself is wrong for this codebase, stop and say which rule and why. A human changes the config.
`skip` lines are not failures, but `missing tool` skips mean the gate is incomplete: say so in the report.

Details per tool, and how to read each output: `references/gates.md`.

## Performance

- Prove claims with numbers from the bench gate, not reasoning.
- Gate on deterministic counts: gungraun (Rust, instruction counts via Valgrind, Linux) or CodSpeed simulation
  mode. Wall-clock numbers on shared machines swing more than most regressions; use them only to investigate.
- To find the cause: `samply` / `cargo flamegraph` / DHAT (Rust), `py-spy` / `memray` / `scalene` (Python),
  `node --cpu-prof` / `--heap-prof` (JS). Fix the hot path, then rerun the bench gate.
- Baselines live in `benches/baselines/` and are protected. A human accepts a new baseline.
- Patterns to look for and to avoid: `references/performance.md`.

## Setting up a repo (human-assisted)

1. `python3 <skill>/scripts/gate.py init` - copies templates (never overwrites without `--force`), vendors the
   runner into `tools/eng-gates/` for CI, adds `.gates/` state to `.gitignore`, prints manual merge steps.
2. `bash <skill>/scripts/install-tools.sh` - installs missing tools for the detected languages and clones
   crapper / dryer / mutator into `~/.local/share/eng-gates/ub`.
3. `gate.py doctor` - every check: `ok` (tool path), `MISS` (install it), `--` (not configured), `off`.
4. Legacy code: run `gate.py full --all` once to see the debt, then keep the default changed-files scope so
   only touched code must meet the bar. Never lower thresholds to make the first run green; scope instead.
5. A human reviews and commits the config. CI runs `gate.py full` with `CI=1` (missing tools fail, local
   approvals are ignored). Protect the same paths with CODEOWNERS / branch protection: the local guard is a
   tripwire, the server-side rule is the lock.

## Config

`gates.toml` in the repo root (protected): base ref, timeout, CRAP / duplication thresholds, tool paths,
per-check `enabled` / `tier` / `cmd` / `requires`, and custom checks (`[check."llm.latency"]`).
The template documents every key.
