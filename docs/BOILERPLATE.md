# Backend boilerplate — what is built, and what is yours

**Status:** M1-0, M1-1, M1-2a, M1-2b, M1-4 and M1-5 are implemented. M1-3 — the
authorization core — is deliberately left as an exercise. See
[M1-3-authorization-task.md](M1-3-authorization-task.md).

This document describes the backend as it exists today: the layers, the files, the request
flow, the invariants it enforces, and the few places where implementation reality differs from
the written spec.

---

## 1. What is implemented vs. what is the exercise

| Area | State | Where |
|---|---|---|
| Config, async engine/session, health routes | Complete | `app/core/config.py`, `app/db/session.py`, `app/main.py` |
| Models, naming convention, FKs/cascades | Complete | `app/models/` |
| Permission catalog + role matrix | Complete | `app/core/catalog.py`, `app/core/enums.py` |
| Idempotent seed + demo data | Complete | `app/db/seed.py` |
| Password hashing, JWTs, refresh tokens | Complete | `app/core/security.py`, `app/services/auth_service.py` |
| Register / login / refresh / logout / me | Complete | `app/api/routes/auth.py` |
| Identity resolution (`get_current_user`) | Complete | `app/api/deps.py` |
| Origin check for refresh/logout | Complete | `app/api/deps.py` |
| **`require_permission` / `require_any_permission`** | **Exercise (stub)** | `app/api/deps.py` |
| **Ownership scoping (`scope_tickets`)** | **Exercise (stub)** | `app/services/ticket_scope.py` |
| Ticket routes + status policy | Complete | `app/api/routes/tickets.py`, `app/services/ticket_service.py` |
| Admin routes + role assignment | Complete | `app/api/routes/admin.py`, `app/services/admin_service.py` |
| Schema, seed, auth tests | Complete | `tests/test_schema.py`, `tests/test_seed.py`, `tests/test_auth.py` |
| Authorization acceptance matrix | Written, skipped until you implement M1-3 | `tests/test_authorization.py` |
| Frontend (M2), Alembic, replies, pagination | Not in scope | — |

The two stubs raise `NotImplementedError` with a contract docstring. The app imports and boots
normally; any RBAC-protected request returns **500** until you implement them. That failure is
intentional: it is the only thing standing between the current boilerplate and a working
authorization layer.

---

## 2. How to run

All backend commands run in **WSL2 Ubuntu 24.04**, never from Windows PowerShell.

```bash
wsl -d Ubuntu-24.04
cd /mnt/c/Users/merss/Documents/RBAC-PROJECT/backend

uv sync                                   # only when dependencies change
uv run python -m app.db.seed              # converge demo data (idempotent)
uv run uvicorn app.main:app --reload --port 8001
```

Then open **http://127.0.0.1:8001/docs** from Windows. Use `127.0.0.1`, not `localhost`.

Quality gates:

```bash
uv run ruff check .
uv run pytest -q                          # 32 passed, 18 skipped
RUN_M1_3=1 uv run pytest tests/test_authorization.py -q
```

The exercise suite is skipped by default so the boilerplate baseline stays green. It turns on
only when you set `RUN_M1_3=1`.

### Demo accounts

Created by `python -m app.db.seed`; the password is `SEED_DEV_PASSWORD`
(default `DevPassw0rd!`, development only):

| Email | Role | Seeded tickets |
|---|---|---|
| `alice@example.com` | customer | 2 (one `open`, one `closed`) |
| `bob@example.com` | customer | 2 (one `in_progress`, one `open`) |
| `staff@example.com` | staff | none |
| `admin@example.com` | admin | none |

Seeding is refused when `APP_ENV=production`, and an existing password hash is never replaced.

---

## 3. Layers and file map

The stack follows `specs/tech-stack.md`: routes never talk to the ORM directly, and services
never know about HTTP.

```
backend/
  app/
    main.py                    FastAPI app, CORS, lifespan create_all, AppError handler, /health
    core/
      config.py                typed settings from backend/.env (fails fast without SECRET_KEY)
      enums.py                 RoleName, PermissionCode, TicketStatus (StrEnum)
      catalog.py               permission catalog + explicit role→permission matrix (seed only)
      security.py              bcrypt cost 12 (threadpool), JWT, refresh token primitives, utcnow
    db/
      base.py                  DeclarativeBase + deterministic constraint naming convention
      session.py               async engine, SessionLocal, get_session (commit/rollback)
      seed.py                  idempotent seed(), SeedReport, demo users/tickets, CLI
    models/
      user.py                  users; roles relationship; role_names / permission_codes
      role.py                  roles; permissions + users relationships
      permission.py            permissions; roles relationship
      ticket.py                tickets; status CHECK; customer FK RESTRICT
      refresh_token.py         hashed token, expiry, revocation, replaced_by_id chain
      associations.py          user_roles, role_permissions (composite PKs, CASCADE)
    schemas/
      auth.py                  Register/Login/Token/User responses; mass-assignment guards
      ticket.py                create/status/response models
      admin.py                 role update, role/permission responses
    services/
      auth_service.py          register, authenticate, issue/rotate/revoke refresh tokens
      ticket_service.py        create/list/get/change_status + transition policy
      ticket_scope.py          ownership predicate — M1-3 EXERCISE
      admin_service.py         list users/roles/permissions, replace role set
      errors.py                AppError hierarchy mapped to HTTP by main.py
    api/
      deps.py                  get_current_user, verify_origin, guards — M1-3 EXERCISE
      routes/
        auth.py                /auth/register login refresh logout me
        tickets.py             /tickets CRUD-ish (M1-4)
        admin.py               /admin users roles permissions (M1-5)
  db/
    setup.sql / setup.sh       databases, least-privilege user, grants
  tests/
    conftest.py                real MySQL test schema, rollback per test, login helper
    test_health.py             /health regression
    test_schema.py             V-01..V-09 schema/constraint assertions
    test_seed.py               V-10..V-19 seed/idempotency/security assertions
    test_auth.py               register/login/refresh/reuse/logout/Origin/mass assignment
    test_authorization.py      M1-3 acceptance matrix (skipped by default)
```

---

## 4. Request flow

Every protected request takes the same path:

```
HTTP request
  └─ route dependency ──► get_current_user
       ├─ HTTPBearer parses `Authorization: Bearer <jwt>`
       ├─ decode_access_token: signature, exp, typ=access (identity claims only)
       ├─ SELECT user WHERE id = sub
       │    └─ selectinload(User.roles).selectinload(Role.permissions)
       └─ returns User (permission_codes resolved from MySQL on this request)
  └─ guard dependency ──► require_permission(...) / require_any_permission(...)
       └─ 403 if the resolved permission set is insufficient
  └─ handler ──► service
       ├─ business rule (e.g. closed is final → 409)
       └─ SQLAlchemy query
            └─ ticket_scope applies the ownership predicate IN SQL
  └─ response schema
```

Consequences worth internalising:

- **The JWT never contains roles or permissions.** A role change is visible on the next
  request; no token reissue is needed. `tests/test_authorization.py` proves this.
- **Deny happens twice for different reasons.** Route guards answer "may this identity attempt
  this operation?" (403). The ownership predicate answers "which rows may this identity see?"
  (foreign id → 404, indistinguishable from missing).
- **404 is not a permission error.** A customer requesting another customer's ticket must get
  404, never 403 — otherwise the endpoint leaks existence.
- **Guards read the database, not the catalog module.** `app/core/catalog.py` describes the
  seed baseline only; it must not be imported by route code to make decisions.

---

## 5. Data model

```
users ──< user_roles >── roles ──< role_permissions >── permissions
  │
  └──< tickets                     refresh_tokens ──► refresh_tokens (replaced_by_id)

CASCADE     user_roles.*, role_permissions.*, refresh_tokens.user_id
RESTRICT    tickets.customer_id        (a user with tickets cannot be deleted)
SET NULL    refresh_tokens.replaced_by_id
```

`tickets.status` is `VARCHAR(20)` plus a named CHECK
(`ck_tickets_ticket_status`) limited to `open`, `in_progress`, `closed`.

The seeded matrix (`app/core/catalog.py`):

| Permission | customer | staff | admin |
|---|:---:|:---:|:---:|
| `ticket:create` | ✅ | | ✅ |
| `ticket:read_own` | ✅ | | ✅ |
| `ticket:read_all` | | ✅ | ✅ |
| `ticket:update_status` | | ✅ | ✅ |
| `user:read` | | | ✅ |
| `user:assign_role` | | | ✅ |
| `role:read` | | | ✅ |

Admin holds every code **explicitly**. There is no `is_superuser` column and no bypass branch.

---

## 6. HTTP surface

| Method | Path | Guard | Notes |
|---|---|---|---|
| POST | `/auth/register` | none | Always assigns `customer`; role-ish fields ignored |
| POST | `/auth/login` | none | Returns 15-min access token + refresh cookie |
| POST | `/auth/refresh` | Origin check | Rotates the refresh token |
| POST | `/auth/logout` | Origin check | Revokes the presented token, clears cookie |
| GET | `/auth/me` | `get_current_user` | Returns roles and permissions from DB |
| POST | `/tickets` | `ticket:create` | Owner taken from identity, never body |
| GET | `/tickets` | `read_own` **or** `read_all` | Ownership predicate in SQL |
| GET | `/tickets/{id}` | `read_own` **or** `read_all` | Foreign id → 404 |
| PATCH | `/tickets/{id}/status` | `ticket:update_status` | `closed` is final → 409 |
| GET | `/admin/users` | `user:read` | Admin only |
| PATCH | `/admin/users/{id}/roles` | `user:assign_role` | Replaces the role set |
| GET | `/admin/roles` | `role:read` | Admin only |
| GET | `/admin/permissions` | `role:read` | Admin only |
| GET | `/health`, `/health/db` | none | Liveness + real MySQL round-trip |

Error mapping lives in `app/services/errors.py` and one handler in `app/main.py`:
`UnauthorizedError` 401, `ForbiddenError` 403, `NotFoundError` 404, `ConflictError` 409,
`SetupError` 503.

---

## 7. Security invariants enforced by the boilerplate

| Invariant | Implementation |
|---|---|
| bcrypt cost 12, off the event loop | `app/core/security.py` (`BcryptHasher(rounds=12)` + threadpool) |
| Access token carries identity only | `create_access_token` writes `sub`, `iat`, `exp`, `typ` |
| Refresh token is opaque and hashed at rest | 256-bit `token_urlsafe`, SHA-256 stored; httpOnly/SameSite=Lax cookie |
| Rotation + reuse detection | `rotate_refresh_token` revokes the old record and walks the chain on reuse |
| Origin allowlist for cookie endpoints | `verify_origin` compares exactly `FRONTEND_ORIGIN`, never a wildcard |
| CORS allowlist | `main.py` uses `allow_origins=[settings.frontend_origin]` with credentials |
| Passwords ≤ 72 bytes | schema validators reject over-long UTF-8 before bcrypt |
| Mass assignment | `extra="ignore"` on registration/ticket schemas; ownership and roles never come from the body |
| Uniqueness | `users.email`, `roles.name`, `permissions.code`, `refresh_tokens.token_hash` |
| No forbidden lazy loads | every relationship is `lazy="raise"`; callers must eager-load explicitly |
| No secrets in logs | seed CLI logs counts only; `.env` is gitignored |

---

## 8. Tests and what they cover

| File | Purpose |
|---|---|
| `tests/conftest.py` | Session-scoped real MySQL engine, schema + seed once; per-test outer transaction rolled back; ASGI client sharing that session; `login` helper |
| `tests/test_health.py` | `/health` smoke |
| `tests/test_schema.py` | Exactly seven tables; CHECK rejects unknown status; three valid statuses; RESTRICT/CASCADE/SET NULL; no `is_superuser` |
| `tests/test_seed.py` | Counts, exact matrix, admin completeness, idempotency (including unchanged password hash), bcrypt cost, production refusal, 72-byte limit |
| `tests/test_auth.py` | Register forces customer; duplicate email; login success/failure; `/auth/me`; cookie flags; rotation; reuse revokes chain; logout; Origin enforcement; mass assignment; JWT carries no grants |
| `tests/test_authorization.py` | **Skipped M1-3 contract:** permission matrix per role, 401 vs 403, foreign-ticket 404 indistinguishability, list scoping, ownership from identity, role changes without re-login, any-of denial for a grantless user, `closed` final |

The test harness deliberately drops only a database whose name ends in `_test`
(`tests/conftest.py`). Never point `TEST_DATABASE_URL` at `rbac_learning`.

---

## 9. Implementation notes and deviations from the spec text

1. **MySQL CHECK violations are `OperationalError`, not `IntegrityError`.**
   MySQL 8 reports error 3819 (`Check constraint violated`) as a `DBAPIError` subclass that
   SQLAlchemy does not map to `IntegrityError`. `test_status_check_rejects_unknown_value`
   therefore asserts `DBAPIError`; the CHECK constraint itself is exactly as specified.
2. **Raw SQL deletes use `expunge_all()`, not `expire_all()`.**
   After a raw `DELETE`, expired ORM objects in the identity map try to refresh on attribute
   access outside the async greenlet, producing `MissingGreenlet`. The cascade tests drop the
   identity-map entries and re-select.
3. **`create_all` is the M1 migration mechanism.** It creates missing tables but never alters
   existing ones. A model change needs an explicit development reset. Alembic is deferred to
   M3+ by the constitution.
4. **Naive UTC timestamps.** MySQL `DATETIME` drops tzinfo, so `utcnow()` returns naive UTC and
   all comparisons stay consistent with the database. The server time zone is forced to
   `+00:00`.
5. **`closed` is final in M1.** `ticket_service._ALLOWED_TRANSITIONS` allows only
   `open → in_progress → closed`; the M3 Pattern Lab may introduce an admin reopen policy.
6. **`tickets` has no `User.tickets` relationship.** This is intentional: `tickets.customer_id`
   is `RESTRICT`, and an ORM relationship would tempt cascade logic that bypasses the database
   rule.
7. **Refresh-token reuse revokes the remaining chain.** `rotate_refresh_token` walks
   `replaced_by_id` forward and revokes every still-active descendant, then returns 401 with a
   cookie-clearing response.
8. **`permission_codes` is a computed property,** not a column. It requires the eager loads
   performed by `get_current_user`; reading it on a non-loaded user raises by design.

---

## 10. Where to go next

Implement the M1-3 contracts in:

- `app/api/deps.py` — `require_permission`, `require_any_permission`
- `app/services/ticket_scope.py` — `scope_tickets`

Then run:

```bash
RUN_M1_3=1 uv run pytest tests/test_authorization.py -q
```

Read [M1-3-authorization-task.md](M1-3-authorization-task.md) first; it contains the exact
contracts, failure semantics, hints, and the acceptance checklist.
