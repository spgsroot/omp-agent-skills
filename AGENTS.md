# AGENTS.md — single structured agent context

> Methodology: multi-agent. You are one terminal in a network of peer omp agents
> (A2A, the fork's base state). Roles live in terminal names and skill groups,
> not in personas. Heavy knowledge lives in the knowledge base and is looked up
> on demand — this file stays the minimum that every request must carry.

## meta

- Revision: 2026-11-06. Structured, machine-readable sections.
- "Search before code" and "ask, don't guess" hold without exceptions.
- Home use = token economy: this file is the floor; details live in the KB.

## principles

1. **Ambiguity → ask.** Unclear requirement/format/behavior/choice — a question,
   not a silent guess. Before irreversible actions (push/MR/deploy) — always.
2. **Search before code.** New stack, versioned APIs, an error without an
   obvious cause — search first. Stuck after 2+ failed attempts — STOP and
   search primary sources.
3. **Secrets** never enter notes, repos, or transcripts; env-only, referenced
   by name. Scan for leaks before pushing new files.
4. **Employer/customer identifiers never enter public repos.** Grep the
   dictionary before every push.

## agents (multi-agent network)

- Every omp terminal runs an A2A bridge on a free port (fork default) with
  auto-registration of peers. The roster: `read agent://`, `/a2a list`.
- **A terminal's role is its name**: `omp --a2a-name builder|reviewer|...` —
  peers see `a2a:<name>` and address tasks by meaning.
- A task for a peer terminal goes to **its main agent** (it decides itself
  whether to answer or spawn subagents); explicit spawning is `a2aSpawn: true`.
- Subagents: one spawn = one clean context; concurrency/budget limits apply
  automatically (ingress guard, refuse policy).

## skills (groups; one catalog, the task picks the group)

| Group | Skills | When |
|---|---|---|
| **dev engineering** | eng-gates; the superpowers cycle (brainstorming, writing-plans, subagent-driven-development, test-driven-development, executing-plans, finishing-a-development-branch, receiving/requesting-code-review, verification-before-completion, systematic-debugging) | code: a project of 3+ tasks → the SDD cycle; a small change — edit+test+commit |
| **reversing** | reversing | any artifact without sources: binaries, bundles, formats, protocols |
| **docs** | writing-docs (READMEs/reports/notes); writing-skills (meta: creating skills) | any user-facing text |
| **coordinating** | coordinating, dispatching-parallel-agents (role: a `--a2a-name coordinator` terminal or whoever fans out) | 3+ agents on one goal: units, waves, tracking, merge |
| **knowledge base** | kb-search, kb-curate | any question about past context: search first, then read |

Skill descriptions are cheap (read on `skill://`); what costs is running the
wrong group for the task. The task's context decides.

## tools (explicit grants above principles)

- `gate.py approve` — without `ENG_GATES_AGENT=1` (it refuses with it). After a
  sanctioned change to protected configs.
- `install-tools.sh --python --ub` — global tools; idempotent.
- Everything else (init in a repo, thresholds, push/MR) — consent first.

## workflow

- **Project** (new feature / 3+ tasks): brainstorming → questions →
  writing-plans → subagent-driven-development (sdd agents) → eng-gates
  (`gate fast` per unit, `gate full` before done).
- **Small change**: edit → test → commit. No SDD.
- **Research**: 3+ independent directions → parallel scouts in one call.
- **After code**: `skill://eng-gates` → `gate fast`; `gate full` before done.

## escalation

Stop and ask on: push/MR to shared repos, deploy, editing shared files,
destructive scope beyond one unit, missing context after a KB search.

## repo-local

An `AGENTS.md` in a repo overrides this file.