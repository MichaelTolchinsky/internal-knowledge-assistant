---
name: public-release-audit
description: Read-only audit before publishing the repository.
disable-model-invocation: true
---

# Public Release Audit

Execute a read-only audit of the repository before pushing to a public remote.

## Inputs

- Working directory root path.
- Specific release candidate branch or commit reference (defaults to current HEAD).

## Steps

1. **Secrets and Credentials Inspection**:
   - Check tracked files for unintended `.env`, private keys, API keys, or embedded passwords.
   - Do not print secret values into logs or terminal output; report file path and line number only.
   - Verify `.env` is listed in `.gitignore`.

2. **Private References & Internal Artifacts**:
   - Scan for internal hostnames, corporate usernames, or private repository identifiers across code, docs, and git history.
   - Ensure placeholder credentials in `.env.example` and `docker/docker-compose.yml` use generic names (e.g. `knowledge_assistant`).

3. **Documentation and Links Validation**:
   - Check that all relative markdown links resolve to existing files.
   - Verify `LICENSE` exists and contains a valid open-source license.
   - Verify `README.md` provides complete local onboarding instructions matching actual repository scripts.

4. **Clean Git State and Artifacts**:
   - Ensure build caches (`__pycache__`, `.pytest_cache`, `.ruff_cache`), virtualenvs, and test artifacts are untracked.

5. **CI Consistency Check**:
   - Verify GitHub Actions workflows match documented commands (`ruff check`, `ruff format --check`, `pytest`, `alembic upgrade head`).

## Outputs

Provide an audit report grouped under these exact headings:
- **Secrets & Credentials Status**: `PASS` or list of offending file paths.
- **Private Identifiers Status**: `PASS` or list of detected internal terms.
- **Documentation & License Status**: `PASS` or missing files / broken links.
- **CI & Hygiene Status**: `PASS` or discrepancies.

## Completion Criteria

- All audit check steps are executed systematically across tracked files.
- The output report is produced with all four required status headings.
- No secret values or sensitive tokens are displayed in the audit output.

## Stop and Failure Conditions

- If any active secret, credential, token, or private key is detected, abort release readiness immediately.
- If tracked files contain uncommitted changes or broken relative documentation links, stop and report.
