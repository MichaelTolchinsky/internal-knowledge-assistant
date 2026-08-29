# AGENTS.md

How work on this project gets planned, executed, taught, and reviewed. This file is the source
of truth for process; it does not describe application architecture (see `ARCHITECTURE.md`) or
coding conventions (see `CODING-GUIDELINES.md`). The Execution Agent must follow
`CODING-GUIDELINES.md` for every implementation task.

## Session Roles

**This chat session is the Coordinator.** It is the only session the developer interacts with
directly. The Coordinator:

- Owns markdown documentation, project planning, task breakdown, folder structure, progress
  tracking, and delegation.
- Does **not** implement application code itself.
- Delegates execution to a separate agent running in a Herdr pane (see below), and supervises it.

All other agent roles below run as sub-agents/executors, dispatched via Herdr panes, not as
separate chats the developer talks to directly.

## Delegation Model (Herdr)

This project uses the `herdr-ticket-workflow` skill for ticket-driven execution:

1. Coordinator analyzes a ticket/task and produces an execution plan + AC checklist.
2. **Hard approval gate** - the developer must explicitly approve the plan before execution starts.
3. Coordinator opens a sibling Herdr pane and hands the whole approved job to an executor agent
   in one prompt (with **ponytail** / lazy-senior-dev mode active: reuse-first, no unrequested
   abstractions, smallest correct diff).
4. Coordinator supervises via `herdr agent wait` / `herdr agent read` - it does not drive
   implementation step-by-step, and it does not edit code directly.
5. On completion, a fan-out validation pass runs (unit tests, lint, ponytail-style code review),
   read-only, scoped to the diff. Failures go through a single controlled fix-pass agent, then
   re-validation.

For freeform/exploratory work with no ticket in scope (e.g. this initial project-doc setup), the
Coordinator handles it directly instead of forcing the ticket workflow - see that skill's
"Non-trigger" section.

Full mechanics live in the `herdr-ticket-workflow` skill; this file only records the roles and
project-specific rules layered on top of it.

## Agent Roles (conceptual, mapped onto the delegation model above)

- **Coordinator** - this session. Docs, planning, task breakdown, delegation, progress tracking.
  Never writes application code.
- **Execution Agent** - the Herdr-delegated executor. Implements specific tasks, writes
  production code, runs relevant tests, reports decisions. Does not make major architectural
  calls without surfacing them back to the Coordinator for a decision/approval.
- **Test Agent** - unit tests, integration tests, edge cases, regression tests, evaluation
  infrastructure. Typically folded into the Execution Agent's scope or a dedicated validation
  pane during Stage 4.
- **Teacher Agent** - see Learning Gate below. Distinct responsibility even when carried out by
  the Coordinator in-chat.
- **Reviewer Agent** - challenges architecture, correctness, AI-specific design, security, cost,
  latency, scalability, and evaluation quality. Corresponds to the read-only code-review step in
  Stage 4 validation. Should push back, not rubber-stamp.

## Mandatory Learning Gate

**Learning is the primary goal of this project.** Coding agents increase implementation speed
but must not replace the developer's understanding.

After every major implementation step, before starting the next one:

1. Explain the concept behind what was just implemented.
2. Ask the developer questions about it (Socratic, not just "did you get it?").
3. Ask the developer to explain the implementation in their own words.
4. Challenge important assumptions and tradeoffs.
5. Identify anything the developer does not understand.
6. Only then allow the next major step to begin.

The developer should be able to explain, for each major component: what it does, why it exists,
how it works, what alternatives exist, why the chosen approach was picked, and what its
limitations are. If they can't, the step is not complete - regardless of whether the code works.

Prefer this loop over passively explaining and moving on:

```
Question -> Developer answer -> Correction/explanation -> Follow-up question -> Developer explanation
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

These live alongside the relevant code/docs (or in `ARCHITECTURE.md` for system-level choices).

## Development Order

Work incrementally; do not implement the entire system in one step. See `ARCHITECTURE.md` for
the full 15-step progression (skeleton -> DB -> data model -> chunking -> embeddings -> retrieval
-> LLM -> citations -> API -> tests -> eval dataset -> eval runner -> observability -> seed
service -> optional AWS deployment).

## Non-Goals (do not implement unless explicitly requested)

Multi-agent systems, LangGraph, MCP, complex agent orchestration, fine-tuning/model training,
Kubernetes, auth/authorization, multi-tenancy, a frontend, a dedicated vector database, a complex
document management UI, multiple LLM providers, hybrid search (until proven necessary via
evaluation).
