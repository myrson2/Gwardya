# Constitution — RBAC Learning Project

**Status:** Ratified v1.1 · **Ratified:** 2026-11-11 · **Scope:** M1–M3
**Change rule:** amendments require a dated note in this file explaining what changed and why.

## 1. Core Philosophy & Axioms

1. **The backend is the only gate.** The frontend may hide buttons; it never decides access.
   Every protected route re-checks identity, permission, and ownership server-side.
2. **One identity, many roles.** A single `users` table owns authentication.
   Customer/staff/admin are roles, not separate tables or login paths.
3. **Permissions are data, not code.** Route bodies never branch on role names.
   Access is granted by permission codes stored in MySQL (`ticket:read_all`, `user:assign_role`, ...).
4. **Explicit admin, no bypass.** The `admin` role holds every permission explicitly.
   No `is_superuser` shortcut, no `if role == "admin"` special case.
5. **Deny by default.** A route without a declared permission is either public by explicit
   choice or inaccessible. Silence never means "allowed".
6. **Small runnable increments.** Every work session ends with the app starting and the
   relevant checkpoints passing. No half-migrated states.
7. **Specs precede code.** Behaviour changes update these specs before implementation.
8. **Patterns must solve a present problem.** No pattern before its pain. A factory, strategy,
   or guard is added only when a real duplication or variation exists, and the rejected
   alternative is recorded in `specs/design-patterns.md`.

## 2. Security & Auth Invariants

### 2.1 Tokens
- **Access token:** JWT, HS256, 15-minute lifetime. Claims: `sub` (user id), `iat`, `exp`,
  `typ="access"`. It carries **no roles or permissions**.
- **Refresh token:** opaque 256-bit random value, 7-day lifetime, delivered only as an
  `httpOnly`, `SameSite=Lax`, `Path=/auth` cookie (`Secure` in production).
- Refresh tokens are stored **hashed** (SHA-256) in `refresh_tokens`; plaintext exists only
  in the cookie.
- **Rotation:** each successful refresh revokes the presented token and issues a replacement
  (`replaced_by_id`).
- **Reuse detection:** presenting an already-rotated token revokes the replacement chain and
  forces re-login.
- **Revocation:** logout revokes the current refresh token and clears the cookie.
- Refresh/logout endpoints are **POST-only** and verify `Origin` against the configured
  frontend origin.

### 2.2 Passwords
- Hashed with **bcrypt** via `pwdlib[bcrypt]` (cost factor 12); plaintext is never logged,
  stored, or returned.
- bcrypt accepts at most **72 bytes** of input. Passwords longer than that are rejected at
  validation time (count UTF-8 bytes, not characters).
- Hash and verify calls run through `run_in_threadpool` — CPU-bound crypto must not block
  the event loop.
- Minimum length 8 characters; maximum 72 UTF-8 bytes. Login failures return a generic
  `"Invalid email or password"` (no user enumeration).

### 2.3 Authorization semantics

| Situation | Response |
|---|---|
| Missing, malformed, or expired access token | **401** |
| Valid identity, missing permission | **403** |
| Resource does not exist **or belongs to another customer** | **404** |
| Valid identity, permission granted, ownership satisfied | **2xx** |

- Ownership checks are **query-level** (filter by `customer_id`), not "fetch then compare in
  Python" where avoidable. For single-resource reads, fetch with the ownership predicate so a
  foreign id yields 404.
- Staff/admin `read_all` bypasses the ownership filter; it does not bypass the permission check.

### 2.4 Registration & role assignment
- Public registration **always** assigns the `customer` role server-side.
- Any client-supplied `role`, `roles`, `permissions`, or `is_superuser` field is ignored and
  covered by a regression test.
- Only a holder of `user:assign_role` may change roles, via the admin API.

### 2.5 Transport & configuration
- CORS allowlist is exactly `http://localhost:5173`, with credentials enabled. No wildcard.
- `SECRET_KEY` is a 256-bit random value in `backend/.env`; `.env` is gitignored.
  `.env.example` contains placeholders only.
- No secrets, tokens, or password hashes in logs.

## 3. Data Integrity & Database Standards

- MySQL 8.0, InnoDB, `utf8mb4`, UTC timestamps.
- Async only: `create_async_engine` + `AsyncSession`, one session per request,
  `expire_on_commit=False`.
- Relationships are loaded explicitly (`selectinload`) — **no implicit lazy loading** in
  async code.
- Foreign keys:
  - `user_roles`, `role_permissions`, `refresh_tokens` → `ON DELETE CASCADE`
  - `tickets.customer_id` → `ON DELETE RESTRICT` (a user with tickets cannot be deleted)
- Uniqueness: `users.email`, `roles.name`, `permissions.code`, `refresh_tokens.token_hash`.
- Ticket status is one of `open`, `in_progress`, `closed`; `closed` is final in M1.
- Every request transaction is committed on success and rolled back on exception.
- `create_all` is the M1 schema mechanism. Alembic is deliberately deferred to M3+.

## 4. Testing Invariants

- The **permission matrix** is executable: for every role × endpoint, the expected status is
  asserted.
- Required regression tests: IDOR (customer B's ticket → 404), revoked refresh token rejected,
  rotated token reuse revokes the chain, registration cannot self-assign admin.
- A password longer than 72 UTF-8 bytes is rejected with 422, not silently truncated.
- Tests run against a dedicated `rbac_learning_test` schema with real MySQL/asyncmy; each test
  is rolled back.
- No test may touch the development or production schema.

## 5. M1 Scope Discipline

**In scope**
- Single `users` identity table; `roles`, `permissions`, join tables.
- bcrypt registration/login; 15-min access JWT; rotating refresh cookie; logout.
- `require_permission(code)` dependency factory; DB-resolved roles/permissions.
- Tickets: create, list own/all, read own/all, change status (staff).
- Admin API: list users, assign roles, list roles/permissions.
- React frontend: login, three dashboards, route guards, permission-driven UI, Access Inspector.
- Pytest permission matrix.

**Out of scope (forbidden in M1)**
- Separate customer/staff/admin tables or login endpoints.
- `is_superuser` bypass, role-name checks in route bodies.
- Access tokens in `localStorage`; stateless refresh tokens.
- Ticket replies, attachments, assignment, priority, complex pagination.
- Email verification, password reset, OAuth/social login, MFA.
- Multi-tenancy/organisations, WebSockets, background workers.
- Docker, Alembic, Redis/caching, microservices, message queues.
- Sync SQLAlchemy sessions or blocking DB calls on the event loop.
- Speculative design patterns (Factory/Strategy before a real variation exists).

## 6. Definition of Done (every increment)

1. App boots and `/docs` loads.
2. Relevant tests pass.
3. No secrets committed.
4. Specs updated if behaviour changed.
5. You can explain the change in your own words (Socratic checkpoint).

## 7. Amendments

- **2026-11-11 — v1.1:** Added axiom 8 (patterns must solve a present problem), the
  `specs/design-patterns.md` learning appendix, and the M3 Pattern Lab. No change to M1 scope.
  Reason: design-pattern study requested; kept out of M1 to avoid over-engineering.
