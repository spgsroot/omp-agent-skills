# Gate reference

Each check: what it catches, the command it runs, how to read a failure, the usual real fix.
When gates are selected for the task, tier `fast` checks each work unit and `full` adds the slow checks.
Scope includes additions, modifications, deletions and renames since the merge-base with `gate.base`
(default `origin/main`), plus staged, unstaged and untracked files. `--all` = whole tree.
Deleted source files still trigger their language's project-wide checks, but are not passed to file linters.
Changes to language configuration trigger all checks for that language. An explicitly configured
base or `--base` that cannot be resolved is a configuration error (exit 2), not an empty diff.
The CI template checks the whole tree on push; pull requests use the target branch's merge-base.

## Guards (all languages, fast)

### guard.config
Fails when a protected file or section differs from the base: `gates.toml`, `tools/eng-gates/**`, `clippy.toml`,
`deny.toml`, `rustfmt.toml`, `rust-toolchain.toml`, `ruff.toml`, `.importlinter`, `tach.toml`, `pyrightconfig.json`,
`mypy.ini`, `.coveragerc`, `eslint.config.*`, `.dependency-cruiser.*`, `knip.json`, `.size-limit.*`, `tsconfig*.json`,
`vitest.config.*`, `jest.config.*`, benchmark baselines, CI workflows, `.pre-commit-config.yaml`;
`Cargo.toml` `[lints]` / `[workspace.lints]` / `[profile]`; `pyproject.toml` `[tool.ruff|mypy|pyright|importlinter|pytest|coverage|deptry|tach]`;
`package.json` `eslintConfig`, `size-limit`, `knip`, `scripts.test|lint|typecheck`.
Sections are compared as parsed data, so reformatting `pyproject.toml` or adding a dependency does not trip it.
Deleting or renaming a protected file also fails the guard.
Fix: revert. A human who agrees with the change runs `gate.py approve` (records hashes in `.gates/approved.json`,
ignored when `CI` is set) or commits it to the base branch.
An approval matches exact file/section identities and content; deleting a protected file is recorded
explicitly. A later edit invalidates that approval. Config and approval files are UTF-8.
When using `--base <ref>` for a run, use the same override for the human `approve` command.
The snapshot and validation use that effective base, including committed deletions.

### guard.suppress
Scans added lines for new suppressions:
- Rust: `#[allow(..)]`, `#[expect(..)]`, `#![allow]`, `#[ignore]`, `cfg_attr(.., allow)`
- Python: `# noqa`, `# type: ignore`, `# pyright: ignore`, `# pragma: no cover`, `pytest.mark.skip|xfail`, `pytest.skip(`
- JS/TS: `eslint-disable`, `@ts-ignore`, `@ts-expect-error`, `@ts-nocheck`, `.skip(`, `istanbul|c8|v8 ignore`, `as any`
- Always fails: `.only(`, `fdescribe(`, `fit(`
A line that also contains `gate-allow: <reason>` becomes a WARN listed for the reviewer instead of a FAIL.
Rename detection is preserved: moving a source file does not make its unchanged suppressions new.
Filenames are passed as literal Git pathspecs, including wildcard characters and `:(...)` prefixes.

## Rust

| id | tier | command | notes |
|---|---|---|---|
| rust.fmt | fast | `cargo fmt --all --check` | fix: `cargo fmt --all` |
| rust.clippy | fast | `cargo clippy --workspace --all-targets --all-features -- -D warnings` | lints from `Cargo.toml` `[workspace.lints]`, thresholds in `clippy.toml` |
| rust.test | fast | `cargo nextest run` (falls back to `cargo test`) | nextest isolates tests per process: flaky shared state shows up |
| rust.deny | full | `cargo deny check` | advisories, licenses, banned crates, unknown sources |
| rust.machete | full | `cargo machete` | unused dependencies |
| rust.semver | full, off | `cargo semver-checks` | turn on for published crates |
| rust.bench | full, off | your `cmd`, e.g. `cargo bench --bench hot_paths` | gungraun regression limits make `cargo bench` exit non-zero |

Clippy lints that matter most for extensibility: `cognitive_complexity`, `too_many_lines`, `too_many_arguments`,
`type_complexity`, `excessive_nesting`, `large_enum_variant`. For performance: `redundant_clone`, `large_futures`,
`needless_collect`, `large_types_passed_by_value`, `trivially_copy_pass_by_ref`, `inefficient_to_string`.
`unwrap_used` / `expect_used` / `panic` fail in library code and are allowed in tests (`clippy.toml`).

## Python

| id | tier | command | notes |
|---|---|---|---|
| py.format | fast | `ruff format --check <changed .py>` | fix: `ruff format` |
| py.lint | fast | `ruff check <changed .py>` | `ruff check --fix` for safe autofixes, then read what is left |
| py.types | fast | `pyright` (or `mypy .`) | runs on the project, not only changed files |
| py.test | fast | `pytest -q -x` | stops at the first failure |
| py.imports | fast | `lint-imports` (or `tach check`) | contracts in `.importlinter` |
| py.deps | full | `deptry .` | missing, unused, transitive-only dependencies |
| py.bench | full, off | `pytest benches --benchmark-only --benchmark-compare=<id> --benchmark-compare-fail=mean:5%` | save a baseline first with `--benchmark-save` |

Ruff rule groups chosen for extensibility: `C90` (complexity 10), `PL` (args 5, branches 10, statements 40,
nesting 4), `FBT` (boolean flags in signatures), `ARG`, `ANN` (typed public API), `TID` (absolute imports).
For performance and serving code: `PERF`, `ASYNC` (blocking calls such as `time.sleep` or sync HTTP inside
`async def`), `B`. `T20` keeps `print` out of library code.

import-linter contract types: `layers` (higher may import lower only), `forbidden` (domain must not import
providers / frameworks), `independence` (adapters do not know each other).
Tach is an alternative; the original gauge-sh repository is unmaintained, development continues in the tach-org fork.

## JS / TS

| id | tier | command | notes |
|---|---|---|---|
| ts.types | fast | `tsc --noEmit -p .` | extend `tsconfig.strict.json` |
| ts.lint | fast | `eslint --max-warnings 0 <changed files>` | type-aware rules need `parserOptions.projectService` |
| ts.test | fast | `vitest run` (or `jest --ci`) | |
| ts.deps | fast | `depcruise src --config .dependency-cruiser.cjs` | cycles, layers, adapter independence, dev deps in runtime code |
| ts.knip | full | `knip` | unused files, exports, dependencies |
| ts.size | full | `size-limit` | only when `.size-limit.*` exists (libraries, frontends) |
| ts.bench | full, off | your `cmd` | pair with `bench_compare.py` |

`verbatimModuleSyntax` in `tsconfig.strict.json` requires ESM (`"type": "module"`) or explicit `.cts` files;
drop it for CommonJS packages. `exactOptionalPropertyTypes` is the strictest flag; legacy code may need it off.

## Uncle Bob's tools (ub-mode), full tier, all three languages

| id | command | fails when |
|---|---|---|
| ub.crap | `crapper --changed --threshold 10` | exit 2: worst CRAP among analysed functions above threshold |
| ub.dry | `dryer --changed --threshold 0.8` | any `DUPLICATE score=` line (dryer itself always exits 0; the runner parses it) |
| ub.mutate | `mutator --changed` | exit 3: a mutant survived; exit 2: baseline tests fail |

CRAP = CC² × (1 − coverage)³ + CC. A function with complexity 4 and no tests scores 20; the same function fully
covered scores 4. Lower it by testing branches, splitting the function, or both.
crapper and mutator generate coverage themselves (cargo-llvm-cov, coverage.py, vitest/c8) and may install those
tools when missing. A failed test run is scored as 0% coverage: if every function suddenly has CRAP = CC² + CC,
fix the test run first. `--changed` analyses whole changed files, so an old complex function next to your edit
can fail the gate: split it (boy-scout rule) or ask whether to scope it out.
mutator runs every covered mutant on its first run; later runs are differential. Start on one file.
Windows: the ub launchers are POSIX sh scripts with a hard-coded `.venv/bin`; gate.py reports them as a missing
tool there instead of crashing, and `install-tools.sh --ub` skips them.

## Stage matrix

Principle: agent work is validated by deterministic tools run locally; numbers are interpreted by the human or a
reviewer agent, never "by eye". Profilers only on suspicion, never in gates; mutation testing targeted, not
repo-wide.

| Check | Rust | Python | JS/TS | Stage |
|---|---|---|---|---|
| Format/lint/types | rustfmt + clippy -D warnings | ruff (format+check) + pyright strict | eslint --max-warnings 0 + tsc --noEmit | fast |
| Tests | cargo-nextest | pytest -q -x | vitest run | fast |
| Module boundaries | workspace crates + cargo-deny (bans) | import-linter | dependency-cruiser | fast |
| Dead code/deps | cargo-machete | deptry | knip | full |
| Public API | cargo-semver-checks (published crates only) | - | api-extractor (libraries only) | full |
| Complexity | clippy::cognitive_complexity | ruff C901/PLR091x | eslint complexity | fast (via linter) |
| CRAP/duplication | crapper + dryer (ub set) | crapper + dryer | crapper + dryer | full, targeted |
| Mutations | cargo-mutants OR mutator | mutmut OR mutator | Stryker OR mutator | full, targeted |
| Microbenchmarks | divan (CodSpeed mode) OR criterion | pytest-codspeed OR pytest-benchmark | tinybench | full, hot-path only |
| Profiling (never a gate) | flamegraph, DHAT, samply | py-spy, scalene, memray | node --cpu-prof | on suspicion |

When gates are selected: `fast` per unit = format+lint+types+tests+boundaries. `full` before done = + dead code, semver
(published), CRAP/mutate on the riskiest file (not the whole repo), benchmarks only when the unit touched a hot
path. Wall-clock on a noisy machine is not a gate; deterministic counters are (CodSpeed simulation / gungraun /
saved baseline + budget). Don't stack linters: ruff covers py format+lint+complexity; eslint covers ts.

## Exit codes

`gate.py`: 0 no failures, 1 a check failed, 2 usage or config error. `bench_compare.py`: 0 within budget,
1 regression or missing benchmark, 2 bad input.
Benchmark metrics must be finite JSON numbers (not booleans, NaN or infinities);
`--max-regression` must be a finite non-negative percentage. Invalid inputs exit 2 instead of reporting success.

## Tool processes

Checks run without a shell. On Windows, npm `.cmd` shims are resolved to their JavaScript entry point
and run with Node so source filenames remain literal arguments. Extensionless Node-shebang entries,
including TypeScript's `bin/tsc`, are supported. Other batch files are rejected; configure a native
executable instead. Cargo plugins use their resolved executable, including `[tools]` pins.

A timeout returns code 124 and preserves captured stdout/stderr. POSIX checks run in a new process group;
Windows checks start suspended, join a kill-on-close Job Object, then resume. Cleanup terminates ordinary
descendants even if their immediate parent already exited. This is process-lifetime management, not a
security sandbox: external service-mediated launches can escape it.

`init` preserves existing files unless `--force` is supplied. The vendored runner includes its templates,
so re-running `init` works without the original skill directory.
