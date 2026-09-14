## Description

Brief summary of changes and engineering rationale.

## Checklist

- [ ] **Scope**: Changes are surgical and match the requested task. No unrelated refactoring.
- [ ] **Protocol Boundaries**: Any new or modified boundaries adhere to `typing.Protocol` rules and explicit subclassing.
- [ ] **Configuration**: No raw default values baked into Python source code; `.env.example` updated if new settings were introduced.
- [ ] **Documentation**: Docs reflect current behavior; no internal document paths or step numbers in code comments.
- [ ] **Testing**:
  - [ ] Targeted unit tests added or updated.
  - [ ] `pytest tests/ -q -m "not requires_real_llm"` passes.
  - [ ] If DB or integration touched: migrations applied and full `pytest tests/` passes.
- [ ] **Linting & Formatting**:
  - [ ] `ruff check src tests migrations seed` passes.
  - [ ] `ruff format --check src tests migrations seed` passes.
- [ ] **RAG Safety & Trust**:
  - [ ] Injection mitigation verified (e.g. `<document>` tag wrapping).
  - [ ] Grounding and clean abstention preserved on missing context.
