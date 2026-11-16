# M1-1 — Validation Strategy

**Status:** Approved · **Milestone:** M1-1 · **Date:** 2026-11-13
**Triad:** [specification.md](specification.md) · [implementation.md](implementation.md) · [validation.md](validation.md)

---

## 1. Automated Test Matrix

All tests run against the real `rbac_learning_test` MySQL schema. Each test is rolled back;
the schema and seed baseline are created once per session.

| ID | Test | Layer | Assertion |
|---|---|---|---|
| **V-01** | `test_schema_has_expected_tables` | Schema | Exactly `users`, `roles`, `permissions`, `user_roles`, `role_permissions`, `tickets`, `refresh_tokens` exist. |
| **V-02** | `test_users_email_is_unique` | Constraint | Duplicate email raises `IntegrityError`. |
| **V-03** | `test_status_check_rejects_unknown_value` | Constraint | Raw `status='bogus'` raises `IntegrityError`. |
| **V-04** | `test_status_accepts_three_valid_values` | Constraint | `open`, `in_progress`, `closed` all insert successfully. |
| **V-05** | `test_ticket_customer_fk_is_restrict` | Constraint | Inspector reports `RESTRICT`; raw user delete raises `IntegrityError`. |
| **V-06** | `test_association_fks_are_cascade` | Constraint | Both `user_roles` FKs and both `role_permissions` FKs report `CASCADE`. |
| **V-07** | `test_refresh_tokens_cascade_with_user` | Constraint | Deleting a user removes their refresh tokens. |
| **V-08** | `test_replacement_pointer_is_set_null` | Constraint | Inspector reports `SET NULL`; deleting a parent token nulls the child pointer. |
| **V-09** | `test_users_have_no_superuser_column` | Constitution | `is_superuser` is absent from `users`. |
| **V-10** | `test_seed_creates_expected_rows` | Seed | 3 roles, 7 permissions, 11 grants, 4 users, 4 tickets. |
| **V-11** | `test_role_permission_matrix_is_exact` | Seed | Customer `{create, read_own}`; staff `{read_all, update_status}`; admin all seven. |
| **V-12** | `test_admin_holds_every_catalog_permission` | Constitution | `admin.permissions == set(PermissionCode)`. |
| **V-13** | `test_catalog_descriptions_are_present` | Seed | Every role and permission has a non-empty description. |
| **V-14** | `test_seed_is_idempotent` | Seed | Second run reports zero creations; counts and IDs unchanged. |
| **V-15** | `test_seed_does_not_overwrite_password_hash` | Security | Hash captured before re-run equals hash after. |
| **V-16** | `test_seed_tickets_cover_both_customers_and_all_statuses` | Seed | Alice 2, Bob 2; statuses = all three. |
| **V-17** | `test_seed_refuses_production` | Security | `APP_ENV=production` raises `RuntimeError`. |
| **V-18** | `test_demo_password_is_bcrypt_cost_12` | Security | Hash starts `$2b$12$`; verifies against `DevPassw0rd!`. |
| **V-19** | `test_health` | Regression | Existing `/health` test still passes. |

### Notes on tricky assertions

- **V-03 / V-05 / V-07 / V-08** use raw SQL so ORM validation or relationship cascades cannot
  mask the database behaviour.
- **V-05** asserts both the inspector's `ondelete` option and the actual delete failure.
- **V-08** re-selects the child in a fresh query after the parent delete so the ORM identity
  map does not serve a stale pointer.
- **V-14** calls `session.expire_all()` between seed runs so the second run hits the database
  instead of the identity map.
- **V-18** normalises the MySQL-returned naive `DATETIME` only where timestamps are asserted.

---

## 2. Constitution Compliance Matrix

| Invariant | Status | Evidence |
|---|---|---|
| **Single auth gateway** (`get_current_user`) | **N/A — M1-2a** | No routes exist yet. The single `users` table and associations are ready for it. |
| **IDOR masking** (foreign resource → 404) | **N/A — M1-3/M1-4** | No endpoints yet. `tickets.customer_id` is indexed so ownership predicates are query-level later. |
| **Session token security** (hashed refresh, no JWT storage) | **Compliant** | `refresh_tokens.token_hash` is unique and sized for SHA-256 hex; no plaintext or JWT column. |
| **Async discipline** (no blocking DB calls) | **Compliant** | All schema and seed work uses `AsyncSession`; engine is `create_async_engine`. |
| **Worker threadpool for bcrypt** | **Compliant for seed** | Seed hashes via `run_in_threadpool(BcryptHasher(rounds=12).hash, ...)`. Runtime hashing lands in M1-2a. |
| **Batch migration discipline** | **N/A — M1 exception granted** | Constitution §3 explicitly makes `create_all` the M1 mechanism; Alembic is deferred to M3+. MySQL has no SQLite batch-render concern. |
| **FK cascades** | **Compliant** | `user_roles`, `role_permissions`, `refresh_tokens.user_id` → `CASCADE`; `tickets.customer_id` → `RESTRICT`; `replaced_by_id` → `SET NULL`. |
| **Uniqueness** | **Compliant** | `users.email`, `roles.name`, `permissions.code`, `refresh_tokens.token_hash`. |
| **Admin explicit, no bypass** | **Compliant** | No `is_superuser` column; admin matrix lists all seven codes; V-09/V-12 enforce it. |
| **Permissions are data, not code** | **Compliant** | Runtime authorization will read `permissions` rows. Code enums only declare the seed catalog and prevent typos. |
| **Registration mass assignment** | **N/A — M1-2a** | No registration route. The `users` model has no role/superuser input surface. |
| **Deny by default** | **N/A — M1-3** | No protected routes exist yet. |
| **No secrets or hashes in logs** | **Compliant** | Seed logs counts only. `.env` stays gitignored. |
| **`closed` is final** | **Partially — by design** | Schema permits `closed`; transition enforcement is M1-4. No status history table (out of scope). |
| **CORS allowlist unchanged** | **Compliant** | No change to `main.py` CORS configuration. |

### Security / IDOR review answers

- **Security & IDOR check:** not applicable to M1-1 because no HTTP surface is added. The
  schema prepares query-level ownership via `tickets.customer_id` and an index.
- **Authentication dependency:** not applicable. `get_current_user` is M1-2a.
- **Failure modes:** duplicate seed rows, invalid status, user deletion with tickets, and
  refresh-token chain deletion are all covered by tests V-02, V-03, V-05, and V-08.
- **Database migrations:** no Alembic migration. `create_all` is the ratified M1 mechanism;
  the reset procedure is documented in `implementation.md` §5.

---

## 3. Manual QA & Exploratory Runbook

```bash
# WSL
cd /mnt/c/Users/merss/Documents/RBAC-PROJECT/backend

# 1. Quality gates
uv run ruff check .
uv run pytest -q

# 2. Boot against a clean dev schema
uv run uvicorn app.main:app --reload --port 8001
# From Windows: http://127.0.0.1:8001/docs → 200
# In MySQL: SHOW TABLES → 7 tables

# 3. First seed
uv run python -m app.db.seed

# 4. Idempotency proof
uv run python -m app.db.seed
# Expect: zero creations, no duplicate rows
```

```sql
-- Run as rbac_app against rbac_learning
SELECT code FROM permissions ORDER BY code;

SELECT r.name, COUNT(*) AS grants
  FROM roles r
  JOIN role_permissions rp ON rp.role_id = r.id
 GROUP BY r.name
 ORDER BY r.name;

SELECT u.email, r.name
  FROM users u
  JOIN user_roles ur ON ur.user_id = u.id
  JOIN roles r ON r.id = ur.role_id
 ORDER BY u.email;

SELECT status, COUNT(*) FROM tickets GROUP BY status;

SHOW CREATE TABLE tickets\G
SHOW CREATE TABLE refresh_tokens\G
```

### Exploratory checks

1. `tickets` DDL contains `CHECK (... status in ('open','in_progress','closed'))`.
2. `tickets.customer_id` shows `ON DELETE RESTRICT`.
3. `refresh_tokens.replaced_by_id` shows `ON DELETE SET NULL`.
4. `refresh_tokens.user_id` shows `ON DELETE CASCADE`.
5. Seed output contains no password, hash, or token.
6. Re-running seed does not change `users.hashed_password`.
7. Role grant counts are customer 2, staff 2, admin 7.

### Negative checks

```sql
-- Must fail with a CHECK violation
INSERT INTO tickets (title, description, status, customer_id)
VALUES ('bad', 'bad', 'bogus', 1);

-- Must fail with an FK RESTRICT violation
DELETE FROM users WHERE email = 'alice@example.com';
```

---

## 4. Evidence to Capture After Implementation

| Check | Target | Recorded |
|---|---|---|
| `uv run pytest -q` | 19 passed | ☐ |
| `uv run ruff check .` | All checks passed | ☐ |
| First seed | 3 roles, 7 permissions, 11 grants, 4 users, 4 tickets | ☐ |
| Second seed | zero creations | ☐ |
| `SHOW TABLES` | 7 tables | ☐ |
| `SHOW CREATE TABLE tickets` | CHECK + RESTRICT | ☐ |
| `SHOW CREATE TABLE refresh_tokens` | CASCADE + SET NULL | ☐ |
| `/docs` | 200 | ☐ |
| Seed logs | no secrets or hashes | ☐ |

After implementation, this evidence and the file inventory are recorded in
`specs/context.md` per the Feature Specification Triad workflow.

---

## 5. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| `create_all` cannot alter evolved tables | Documented reset procedure; Alembic deferred by constitution. |
| Session-scoped event loop surprises future tests | Explicit `pyproject.toml` config; per-module markers can override later. |
| `lazy="raise"` surfaces as runtime errors | Intended: forces explicit `selectinload`; seed and tests demonstrate the pattern. |
| Seed reconciliation undoes manual role edits | Documented: seed restores the demo baseline; passwords are never reset. |
| Known dev password leaks into production | `APP_ENV=production` refuses to seed; password overridable via `SEED_DEV_PASSWORD`. |
| MySQL `DATETIME` is naive | Tests normalise to UTC; session time zone is forced to `+00:00`. |
| Test fixture drops the wrong schema | Fixture asserts the database name ends in `_test` before `drop_all`. |
| Seed partially writes on failure | Entire seed runs in one transaction; CLI commits only after success. |

---

## 6. Related Documentation

- [specification.md](specification.md) — requirements and acceptance criteria
- [implementation.md](implementation.md) — schema, seed, and test harness design
- [`specs/constitution.md`](../../constitution.md) — source of every invariant above
- [`specs/roadmap.md`](../../roadmap.md) — M1-1 exit criteria
