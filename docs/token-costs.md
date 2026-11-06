# Token-cost analysis of the dev persona (historical, 2026-10-31; the persona layer is gone — see README)

Purpose: where the tokens actually go when you pay per token.

## Static per-session costs (measured)

Measured 2026-10-31 on omp 18.14.0: the first request of `omp -p` inside a git
repo, with the persona installed vs. without it (plugin disabled, user
`AGENTS.md` and append prompt removed). Provider-reported prompt tokens.

| Model | Without persona | With persona | Delta |
|---|---|---|---|
| claude-opus-5-5 | 15 629 | 22 618 | +7.0k (+45%) |
| kimi k3.1-pro | 9 102 | 13 572 | +4.5k (+49%) |

Delta breakdown (o200k estimates; Anthropic's tokenizer counts ~1.3× more):

| Consumer | ~tokens | Notes |
|---|---|---|
| `AGENTS.md` | 1.5k | was 1.9k before the stage matrix moved into `skill://eng-gates/references/gates.md` |
| Superpowers bootstrap (`<EXTREMELY_IMPORTANT>`) | 1.5k | using-superpowers body 0.7k + omp tool mapping 0.8k; injected by the plugin, re-armed after compaction |
| Skill descriptions (16: superpowers + eng-gates) | 0.5k | name+description per skill, always in prompt |
| `persona-dev-prompt.md` | 0.35k | permissions appendix |
| SDD agent descriptions in the `task` tool | 0.25k | five `sdd-*` seats |
| lsp / ast_grep enablement | small | `task.enableLsp`, `astGrep.enabled` |

The bootstrap is plugin-owned; disabling the extension kills the SDD
skill-discovery guidance too - not recommended for the dev persona.
Skill descriptions: add names to `skills.ignoredSkills` for skills you never
read (count `skill://<name>` reads in `~/.omp/agent/sessions` first).

## Per-dispatch costs (the real driver)

| Consumer | ~tokens | Notes |
|---|---|---|
| sdd-implementer system prompt | 0.6k | fixed per seat |
| sdd-reviewer | 1.5k | fixed |
| sdd-rereviewer | 1.2k | fixed |
| sdd-escalation-implementer | 0.8k | fixed |
| sdd-final-reviewer | 1.3k | fixed |
| Dispatch brief (task text + interfaces) | 0.5–2k | **you control this** |
| Subagent working context (reads, tests output) | 5–50k+ | **you control this via scoping** |
| Controller context growth per task result | 0.1–1k | report-file contract keeps it low |

Multiplied by turn count. The upstream fork's measurement on a real fix
re-review: grok-4.6 seat 9.7 min / 4 turns; sonnet-5 50 s / 1 turn;
DeepSeek flash 100 s / 4 turns - same verdict. **Cheap-but-chatty models
lose money on multi-step work.**

## Pitfalls found in real usage (stats.db, 37k requests)

- **Context length dominates.** Main-session prompt median 169k, p90 385k,
  p99 751k; requests at 100–400k carried 81% of main-session cost. With the
  legacy reserve-based threshold (`compaction.thresholdPercent: -1`) 1M-window
  models run to ~750k before compacting. Cap it: `compaction.thresholdTokens`
  ≈ 200–250k.
- **A stray home-level `AGENTS.md` loads into every non-repo session.**
  omp's `agents-md` walk includes `~/AGENTS.md` when cwd is under home and not
  inside a git repo. Tools that "install agent skills" by appending to it (e.g.
  `comfy skills`) silently add tens of thousands of tokens per request
  (measured: +47k). Move such blocks into `~/.omp/agent/skills/<name>/SKILL.md`.
- **Provider cache misses mid-turn.** openai-codex re-sent the full prompt
  uncached on 4.7% of same-model requests < 5 min apart (Anthropic 0%, kimi
  0.9%), mostly while the prompt was growing - provider-side, not omp
  pruning. Budget for it when choosing codex for long tool loops.
- **Tool output weight.** `read` results are the biggest input stream; prefer
  ranged reads and `grep` with tight paths over whole-file reads.

## Levers ranked by impact

1. **Turn count (model choice per seat).** Map `task.agentModelOverrides`
   to YOUR models with a real thinking ladder. Floor for
   sdd-reviewer/sdd-implementer: a mid-tier model. rereviewer can run
   cheap+low (verdict-only work over a small diff). escalation/final -
   your strongest, they run once per plan/stuck task.
2. **Context cap.** `compaction.thresholdTokens` - every turn pays for the
   whole cached context; a 700k session costs ~3× a 250k one per turn.
3. **Brief hygiene.** One task, its interfaces, global constraints.
   The upstream skill ships scripts (`task-brief`) that extract exactly
   one task's text - use them; never paste plan history.
4. **Report-file contract.** Implementers write full reports to a file and
   return ≤12 lines; the controller reads files/`agent://<id>` fields
   only when needed. Never echo full results into chat.
5. **Wave parallelism ≠ token savings.** Parallel waves save wall-clock,
   not tokens. Token savings come from fewer, well-scoped dispatches:
   batch small same-shape edits into one brief.
6. **Compaction.** Each compaction re-pays the static prompt + bootstrap
   (~2k). Long sessions with many small tasks lose more to compaction
   cycles than to the work itself - prefer finishing a task to a ledger
   line and starting fresh dispatches.
7. **`read.summarize`** (omp config): plain `read` summarizes large code
   files to declarations; the SDD seats set `readSummarize: false` because
   they edit what they read. Keep that - a reviewer that missed a hunk
   costs a re-review round (3–5× more than the saved tokens).

## Home-model mapping template

```yaml
task:
  agentModelOverrides:
    sdd-implementer: <your-mid-tier>:high,@task
    sdd-reviewer: <your-mid-tier>:high,@task
    sdd-rereviewer: <your-cheap-tier>:low,@task
    sdd-escalation-implementer: <your-strongest>:max,@slow
    sdd-final-reviewer: <your-strongest>:max,@slow
```

Lead/executor split (strong controller and reviewers, cheaper implementers):

```yaml
modelRoles:
  default: anthropic/claude-opus-5-5:high      # controller = team lead
task:
  agentModelOverrides:
    sdd-reviewer: anthropic/claude-opus-5-5:high
    sdd-rereviewer: anthropic/claude-opus-5-5:high
    sdd-final-reviewer: anthropic/claude-opus-5-5:high
    sdd-implementer: kimi-code/k3.1-pro:high,xai-oauth/grok-4.7:high
    sdd-escalation-implementer: xai-oauth/grok-4.7:xhigh,kimi-code/k3.1-pro:max
```

Use exact catalog ids (`omp models ls <provider>`) and only levels the
model offers - unsupported levels are silently clamped, collapsing the
ladder. An override replaces the whole model list: the comma list is the
seat's fallback chain (`@task` / `@slow` fall back to a role).
