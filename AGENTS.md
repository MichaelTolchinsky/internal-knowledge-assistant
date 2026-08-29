# AGENTS.md

How work on this project gets planned, executed, taught, and reviewed. This file is the source
of truth for process; it does not describe application architecture (see
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)) or coding conventions (see
[`docs/CODING-GUIDELINES.md`](docs/CODING-GUIDELINES.md)). Anyone implementing a task - human or
AI agent - should follow `docs/CODING-GUIDELINES.md`.

This file defines **roles and gates**, not a specific tool's mechanics. Whatever agent, IDE, or
workflow you use to actually write code should be able to follow this process.

## Roles

- **Coordinator** - owns markdown documentation, project planning, task breakdown, folder
  structure, and progress tracking. Does not implement application code.
- **Execution** - implements a specific, approved task: writes production code, runs relevant
  tests, reports back the decisions made. Does not make major architectural calls unilaterally -
  surfaces them as a decision record (see below) instead.
- **Test** - unit tests, integration tests, edge cases, regression tests, evaluation
  infrastructure. Can be the same actor as Execution for a small task.
- **Teacher** - see the Learning Gate below. A distinct responsibility even when carried out by
  whoever is coordinating the work.
- **Reviewer** - challenges architecture, correctness, AI-specific design (grounding, citations,
  abstention), security, cost, latency, and evaluation quality. Should push back, not
  rubber-stamp.

These roles can map onto separate sessions/agents, separate PR reviewers, or just separate
mental modes for a single contributor - the process is the same either way.

## Workflow Shape

1. Analyze the task and produce a short execution plan plus an acceptance-criteria checklist.
2. Get explicit approval on the plan before writing code for anything non-trivial.
3. Implement against the approved plan; keep diffs scoped to it. Escalate rather than guess on
   ambiguous requirements or anything outside the plan's stated scope.
4. Validate with evidence - a passing scoped test run, not just "the edit looks right" - before
   marking an acceptance criterion done.
5. Review (tests, lint, and a focused code review pass) before merging.

## Mandatory Learning Gate

**Learning is the primary goal of this project.** Coding agents increase implementation speed
but must not replace the developer's understanding.

After every major implementation step, before starting the next one:

1. Explain the concept behind what was just implemented.
2. Ask questions about it (Socratic, not just "did you get it?").
3. Ask for the implementation to be explained back in plain language.
4. Challenge important assumptions and tradeoffs.
5. Identify anything that isn't understood yet.
6. Only then move on to the next major step.

For each major component, be able to explain: what it does, why it exists, how it works, what
alternatives exist, why the chosen approach was picked, and what its limitations are. If not,
the step isn't complete - regardless of whether the code works.

Prefer this loop over passively explaining and moving on:

```
Question -> Answer -> Correction/explanation -> Follow-up question -> Explanation
```

Optimize for `Understanding x Practical Experience x Retention`, not lines of code per day.

## Decision Records

For each significant technical decision (chunking strategy, embedding model, top-K, chunk size,
prompt structure, etc.), record:

```
Decision
Options considered
Tradeoffs
Chosen approach
Reason
```

These live alongside the relevant code/docs, or in `docs/ARCHITECTURE.md` for system-level
choices.

## Development Order

Work incrementally; do not implement the entire system in one step. See
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full progression (skeleton -> DB -> data
model -> chunking -> embeddings -> retrieval -> LLM -> citations -> API -> tests -> eval dataset
-> eval runner -> observability -> seed service -> optional AWS deployment).

## Non-Goals (do not implement unless explicitly requested)

Multi-agent systems, LangGraph, MCP, complex agent orchestration, fine-tuning/model training,
Kubernetes, auth/authorization, multi-tenancy, a frontend, a dedicated vector database, a complex
document management UI, multiple LLM providers, hybrid search (until proven necessary via
evaluation).
