# M1-1 — Models & Seed

**Status:** Approved · **Milestone:** M1-1 · **Date:** 2026-11-13
**Triad:** [specification.md](specification.md) · [implementation.md](implementation.md) · [validation.md](validation.md)

---

## 1. Context & Motivation

M1-0 proved the app can reach real MySQL. M1-1 creates the data model every later
authorization decision depends on: one identity table, data-driven roles and permissions,
ownership on tickets, and hashed refresh-token storage. Without a trustworthy schema and an
explicit role→permission matrix, M1-3's `require_permission` would resolve against nothing.

References: [`specs/roadmap.md`](../../roadmap.md) M1-1,
[`specs/constitution.md`](../../constitution.md) §2.4/§3/§4, `context.md` §8.

### Decisions locked during discovery

| Question | Decision |
|---|---|
| Scope | M1-1 only — models, seed, `create_all`, schema/seed tests |
| Demo passwords | Known development password, bcrypt cost 12 |
| Permission catalog | README's seven codes; `role:read` gates both admin list endpoints |
| Ticket status | `VARCHAR(20)` + `CHECK` constraint |
| Seed idempotency | Select-then-insert by natural key |
| Sample tickets | Four tickets across both customers and all three statuses |

---

## 2. User Stories

| ID | Story |
|---|---|
| **US-1** | **GIVEN** a clean development schema **WHEN** the app starts **THEN** all seven tables exist with the declared constraints. |
| **US-2** | **GIVEN** a seeded database **WHEN** the seed command runs again **THEN** no duplicate rows are created and existing password hashes are untouched. |
| **US-3** | **GIVEN** a seeded database **WHEN** I query each role's permissions **THEN** customer, staff, and admin match the documented matrix exactly, and admin holds every permission explicitly. |
| **US-4** | **GIVEN** any client, including raw SQL **WHEN** an invalid ticket status is inserted **THEN** the database rejects it. |
| **US-5** | **GIVEN** the test suite **WHEN** it runs **THEN** it proves schema behaviour against the real MySQL test schema and never touches the development schema. |

---

## 3. Functional Requirements

| ID | Requirement |
|---|---|
| **FR-1** | Define `User`, `Role`, `Permission`, `Ticket`, `RefreshToken` with SQLAlchemy 2.0 typed mappings. |
| **FR-2** | Define `user_roles` and `role_permissions` association tables with composite primary keys. |
| **FR-3** | Enforce uniqueness on `users.email`, `roles.name`, `permissions.code`, `refresh_tokens.token_hash`. |
| **FR-4** | Ticket status is a `VARCHAR(20)` restricted by a `CHECK` to `open`, `in_progress`, `closed`. |
| **FR-5** | Run `Base.metadata.create_all` in the FastAPI lifespan. No Alembic in M1. |
| **FR-6** | Provide an explicit idempotent seed CLI: `uv run python -m app.db.seed`. |
| **FR-7** | Seed exactly seven permission codes from the README catalog. |
| **FR-8** | Seed the three roles and reconcile their permission grants on every run. |
| **FR-9** | Seed four demo users and four sample tickets across both customers and all three statuses. |
| **FR-10** | Seed is idempotent: natural-key lookup, no duplicate rows, no password reset on re-run. |
| **FR-11** | Hash the demo password with bcrypt cost 12 via `run_in_threadpool`; never log hashes or plaintext. |
| **FR-12** | Add async test fixtures that create the schema once against `rbac_learning_test` and roll back each test. |
| **FR-13** | Add no HTTP endpoints in this increment; existing `/health*` behaviour is unchanged. |
| **FR-14** | Refuse to seed when `APP_ENV=production`. |
| **FR-15** | Add a seed guard that refuses to drop a schema whose name does not end in `_test`. |

---

## 4. Non-Functional Requirements

- **Security:** no plaintext passwords, no password hashes in logs, no `is_superuser` column,
  admin privileges granted explicitly.
- **Performance:** seed completes in under 5 seconds on a warm MySQL; four bcrypt hashes
  dominate that time.
- **Reliability:** the entire seed runs in one transaction; failure leaves the database
  unchanged.
- **Maintainability:** one catalog module is the single source of role names and permission
  codes; no role strings scattered through models.
- **Async discipline:** every database operation uses `AsyncSession`; crypto runs in a worker
  thread.

---

## 5. Seed Baseline

### Permission catalog

| Code | Description | customer | staff | admin |
|---|---|:---:|:---:|:---:|
| `ticket:create` | Create tickets | ✅ | | ✅ |
| `ticket:read_own` | Read own tickets | ✅ | | ✅ |
| `ticket:read_all` | Read all tickets | | ✅ | ✅ |
| `ticket:update_status` | Change ticket status | | ✅ | ✅ |
| `user:read` | List users | | | ✅ |
| `user:assign_role` | Assign roles to users | | | ✅ |
| `role:read` | List roles and permissions | | | ✅ |

Admin's grant list is written out explicitly, not derived from the catalog. A test asserts
admin equals the full catalog so a newly added permission cannot silently skip admin.

### Demo users

| Email | Full name | Role | Tickets |
|---|---|---|---|
| `alice@example.com` | Alice Customer | customer | 2 |
| `bob@example.com` | Bob Customer | customer | 2 |
| `staff@example.com` | Sam Staff | staff | 0 |
| `admin@example.com` | Ada Admin | admin | 0 |

**Development password:** `DevPassw0rd!` (13 UTF-8 bytes), configurable via
`SEED_DEV_PASSWORD`. The seed refuses to run when `APP_ENV=production`.

### Sample tickets

| Ticket | Owner | Status |
|---|---|---|
| Printer will not connect | Alice | `open` |
| Invoice copy request | Alice | `closed` |
| VPN drops every hour | Bob | `in_progress` |
| Cannot reset password | Bob | `open` |

---

## 6. Acceptance Criteria

- [ ] App boot creates all seven tables on a clean development schema.
- [ ] `SHOW CREATE TABLE tickets` shows the status `CHECK` and `ON DELETE RESTRICT` on
      `customer_id`.
- [ ] `SHOW CREATE TABLE refresh_tokens` shows `ON DELETE CASCADE` for `user_id` and
      `ON DELETE SET NULL` for `replaced_by_id`.
- [ ] First seed creates 3 roles, 7 permissions, 11 grants, 4 users, 4 tickets.
- [ ] Second seed creates zero rows; counts, IDs, and password hashes are unchanged.
- [ ] Admin holds all seven permissions explicitly; customer and staff hold exactly their
      documented sets.
- [ ] Direct SQL with `status='bogus'` fails.
- [ ] Deleting a user who owns tickets fails.
- [ ] Deleting a replaced refresh token sets the child's `replaced_by_id` to `NULL`.
- [ ] `uv run pytest -q` passes, `uv run ruff check .` is clean, `/docs` returns 200.
- [ ] No secret or hash appears in seed output.

---

## 7. Out of Scope

Auth routes, JWT, refresh rotation, `get_current_user`, `require_permission`, ticket
endpoints, admin endpoints, frontend, Alembic, replies, pagination, soft delete, audit
history, `is_active`, email verification, password reset.

---

## 8. Related Documentation

- [`specs/constitution.md`](../../constitution.md) — security, data, and testing invariants
- [`specs/roadmap.md`](../../roadmap.md) — M1-1 exit criteria
- [`specs/tech-stack.md`](../../tech-stack.md) — layer boundaries
- [`context.md`](../../../context.md) §8 — the working M1-1 checklist this spec formalises
