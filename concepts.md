# Concepts — What You Need to Learn to Build Gwardya

**Derived from:** `specs/constitution.md`, `specs/mission.md`, `specs/tech-stack.md`,
`specs/roadmap.md`, `specs/design-patterns.md`
**Status:** Learning guide, not a normative spec. If this file and `specs/` disagree, `specs/` wins.

**How to use this file:** read §0 once, then work top-to-bottom through §2 as you build. Use §3
as the reference when a step feels shaky, §4 when something breaks, and §6 as the oral review you
must pass before calling M1 done. You do not need to learn everything here before writing code —
you need to learn each row *before the step that depends on it*.

---

## 0. The mental model I will code against

Every protected request walks the same four-stage pipeline. Learn this before anything else;
every file in the repo exists to serve one stage.

```
HTTP request
  │
  ├─ 1. IDENTITY      get_current_user      → who are you?      (401 if not provable)
  ├─ 2. PERMISSION    require_permission(c) → may you attempt?  (403 if not granted)
  ├─ 3. OWNERSHIP     service predicate     → is it yours?      (404 if not, never 403)
  └─ 4. BUSINESS RULE policy / service      → is this move legal right now?
```

Six rules that fall out of it, and that I will not break:

1. **The backend is the only gate.** React guards are UX. If I delete the frontend, the API still
   says no.
2. **Permissions are data.** No route body will ever contain the string `"admin"`, `"staff"`, or
   `"customer"`.
3. **Authorization is resolved per request from MySQL**, not read from the JWT.
4. **Ownership is a SQL predicate**, not a Python `if ticket.customer_id == user.id` after fetching.
5. **Deny by default.** A route with no declared permission is public only because I said so.
6. **401 = I don't know you. 403 = I know you, you may not. 404 = you may not even know it exists.**

The one-sentence version: *authentication proves identity, permissions decide capability,
ownership decides reach, and policies decide legality — in that order, every time.*

---

## 1. Concept map

### 1.1 Python & async runtime

| Concept | Why it matters here | Where you'll see it |
|---|---|---|
| Event loop, coroutines, `await` | Every DB call and hash is async or threadpooled | `app/main.py`, all services |
| Blocking vs non-blocking work | bcrypt at cost 12 is ~100ms of CPU; blocking the loop stalls all requests | `app/core/security.py` |
| `run_in_threadpool` / `anyio.to_thread` | Correct way to run bcrypt without freezing the loop | password hash + verify |
| Context managers (`async with`) | Session lifetime and rollback guarantees | `get_session` dependency |
| Exceptions & exception handlers | Mapping domain failure → HTTP status in one place | `app/main.py` |
| Type hints + `Protocol` | FastAPI reads annotations; Strategy in M3 depends on it | everywhere, M3 policies |

### 1.2 FastAPI

| Concept | Why it matters here | Where you'll see it |
|---|---|---|
| Dependency injection (`Depends`) | The whole authorization design is a dependency graph | `app/api/deps.py` |
| **Dependency factory / closure** | `require_permission("x")` returns a guard that captures `x` | `app/api/deps.py` |
| Sub-dependencies | `guard → get_current_user → get_session` chains automatically | same |
| `HTTPException` + status codes | 401/403/404 semantics are contract, not decoration | routers + deps |
| `APIRouter` + prefixes/tags | Route layout and Swagger grouping | `app/api/routes/` |
| Pydantic v2 request/response models | The allowlist that stops mass assignment | `app/schemas/` |
| `response_model` + `from_attributes` | Guarantees `hashed_password` never leaves the API | schemas |
| `pydantic-settings` | Typed config from `.env`; fails fast on missing secrets | `app/core/config.py` |
| Lifespan / startup | Where `create_all` and engine disposal happen | `app/main.py` |
| CORS middleware | Exact origin + credentials; no wildcard | `app/main.py` |
| `Header` / `Request` access | Reading `Origin` for refresh/logout CSRF check | auth router |
| `HTTPBearer(auto_error=False)` | Default auto_error returns **403**, which violates the 401 rule | `app/api/deps.py` |
| `/docs` as a test surface | M1 exit gate is a Swagger walkthrough | manual demo |

### 1.3 SQLAlchemy 2.0 async + MySQL

| Concept | Why it matters here | Where you'll see it |
|---|---|---|
| `create_async_engine`, `async_sessionmaker` | Async-only stack; no sync sessions allowed | `app/db/session.py` |
| One `AsyncSession` per request | Transaction boundary = request boundary | `get_session` |
| `expire_on_commit=False` | Objects stay readable after commit without a re-fetch | session factory |
| `select()` 2.0 style + `execute`/`scalars` | All queries are explicit | services |
| **`selectinload` and eager loading** | Lazy loading raises `MissingGreenlet` in async code | permission resolution |
| Many-to-many via association tables | `user_roles`, `role_permissions` have no ORM class needed | models |
| `secondary=` relationships | Clean traversal `user.roles → role.permissions` | models |
| Transaction lifecycle: commit / rollback | Success commits once; exception rolls back | `get_session` |
| FK actions: `CASCADE` vs `RESTRICT` | Deleting a user with tickets must fail loudly | models |
| Unique constraints + indexes | Email, role name, permission code, token hash | models |
| `DateTime(timezone=True)` + UTC | No naive timestamps anywhere | models |
| Idempotent seeding | Re-running `seed.py` must not duplicate rows | `app/db/seed.py` |
| `create_all` (M1) vs Alembic (M3+) | Deliberate deferral, not an oversight | `app/main.py` |

### 1.4 Authentication

| Concept | Why it matters here | Where you'll see it |
|---|---|---|
| Password hashing vs encryption | Hashes are one-way; you never "decrypt" a password | `security.py` |
| bcrypt cost factor + 72-byte limit | Cost 12 is slow on purpose; >72 UTF-8 bytes must be **rejected**, not truncated | schemas + security |
| Salt handling | bcrypt embeds the salt; you store one opaque hash string | security |
| `pwdlib` with explicit `BcryptHasher` | `PasswordHash.recommended()` picks Argon2, so construct bcrypt explicitly | security |
| Constant-ish login failure | Same message for unknown email and bad password (no enumeration) | auth router |
| JWT structure: header.payload.signature | Base64url JSON; readable by anyone, trustworthy only if verified | security |
| HS256 signing vs encryption | JWT is signed, **not** secret — never put PII in it | security |
| Claims: `sub`, `iat`, `exp`, `typ` | `sub` is a string user id; `typ` prevents token confusion | security |
| Why permissions are **not** in the token | Demotion must take effect on the next request, not in 15 minutes | deps |
| Opaque tokens vs JWTs | Refresh tokens are random strings, not JWTs, so they can be revoked | refresh flow |
| `secrets.token_urlsafe(32)` | 256 bits of entropy; the plaintext lives only in the cookie | refresh flow |
| SHA-256 at rest | DB leak must not yield usable refresh tokens | `refresh_tokens.token_hash` |
| Cookie flags: `httpOnly`, `SameSite=Lax`, `Path=/auth`, `Secure` | XSS can't read it, CSRF is limited, it's only sent where needed | auth router |
| Why access token lives **in memory** | `localStorage` is XSS-readable | frontend auth context |
| CSRF + `Origin` check | Cookie-based endpoints need an origin allowlist even with `SameSite` | refresh/logout |

### 1.5 Authorization (the heart)

| Concept | Why it matters here | Where you'll see it |
|---|---|---|
| RBAC: users → roles → permissions | Roles are bundles; permissions are the atomic unit | models + seed |
| Permission code naming (`resource:action`) | Stable contract between DB and code | permission catalog |
| Permission resolution query | Load user with `roles → permissions` per request | `deps.py` |
| Deny by default | Missing guard means "public by choice", never accidental | route inventory |
| 401 vs 403 vs 404 | Three different truths; conflating them leaks or confuses | deps + services |
| **IDOR** (Insecure Direct Object Reference) | Sequential ids make "change the number" attacks trivial | tickets service |
| Query-level ownership predicate | `WHERE id = :id AND customer_id = :me` yields 404 naturally | services |
| `read_all` bypass vs permission bypass | Staff skip the ownership filter, not the permission check | tickets service |
| Role change without token reissue | Proof that permissions are data, not claims | admin API |
| Mass assignment | Client-supplied `role`/`is_superuser` must be ignored by schema design | register schema |

### 1.6 Testing

| Concept | Why it matters here | Where you'll see it |
|---|---|---|
| `pytest-asyncio` (auto mode) | All API tests are async | `tests/conftest.py` |
| `httpx.AsyncClient` + `ASGITransport` | In-process requests, real app, no network | conftest |
| Dependency override | Swap the DB session for a test-scoped one | conftest |
| Transaction-per-test + rollback | Isolation without re-seeding per test | conftest |
| Savepoints when app code commits | `begin_nested()` so a commit doesn't escape the test transaction | conftest |
| Fixtures as roles | `customer_client`, `staff_client`, `admin_client` | conftest |
| **Table-driven permission matrix** | Every role × endpoint × expected status, in one parametrized test | `test_permissions.py` |
| Regression tests as invariants | IDOR, reuse detection, mass assignment, 72-byte password | `tests/` |
| Real MySQL, not SQLite | `ON DELETE`, `utf8mb4`, async driver behavior must match prod | `rbac_learning_test` |
| Time control for expiry | Freeze/patch time or mint an already-expired token | token tests |
| Cookie-jar assertions | Rotation tests must inspect `Set-Cookie`, not just bodies | refresh tests |

### 1.7 Frontend

| Concept | Why it matters here | Where you'll see it |
|---|---|---|
| React 19 hooks + effects | Auth bootstrap and refresh-on-401 are effect-driven | `src/auth/` |
| Context as the auth store | One place owns token, user, permissions | `AuthContext` |
| In-memory token + reload problem | Reload wipes the token → silent refresh on boot | bootstrap effect |
| **Single-flight refresh** | Parallel refreshes rotate twice and trip reuse detection | `src/api/client.ts` |
| `fetch` + `credentials: "include"` | Refresh cookie only travels when explicitly allowed | api client |
| Retry-once-on-401 | Refresh then replay the original request; never loop | api client |
| React Router 7 layouts + `Outlet` | Shared shell, nested dashboards | `App.jsx` |
| `Navigate` + `useLocation` | Redirect to login and back to where you were | guards |
| Guards as UX only | Hiding a button is not security | `RequireAuth`, `RequirePermission` |
| Rendering nav from a permission array | UI mirrors data, not role names | nav component |
| Base64url decoding (no verification) | Access Inspector shows claims; it must never "trust" them | inspector page |
| React StrictMode double-effects | Dev double-invoke can fire two refreshes | bootstrap |
| Vite env vars (`VITE_*`) | API base URL differs per environment | `.env` |

### 1.8 Design patterns

| Concept | Why it matters here | Where you'll see it |
|---|---|---|
| Dependency factory (closure) | Captures a permission code without repeating guards | `require_permission` |
| Strategy pattern | Varying business rules **after** authorization passes | M3 policies |
| Permission vs policy boundary | "May you attempt" vs "is this transition legal" | M3 write-up |
| Pure functions / no DB in policy | Policies must be testable without a database | M3 policies |
| Fail-closed dispatch | Unknown role → deny, never a default-permissive branch | M3 |
| Axiom 8: no pattern before its pain | Factory stays deferred until a real variation exists | `design-patterns.md` |

---

## 2. Build order — what I implement, and what you must learn first

I build in this order because each step's failure mode teaches the next concept. Do not skip
ahead: the auth flow is the hardest part and it depends on the session/transaction model.

| Step | What I build | Learn before | Proof you understood it |
|---|---|---|---|
| **0** | `db/setup.sql`, `.env`, `uv` project, `/health/db` | async engine, grants, config | `/health/db` returns `ok`; app boots without the dev DB user being root |
| **1** | Models + association tables + `create_all` | many-to-many, FK actions, UTC, uniques | You can draw the ERD from memory and say what `RESTRICT` does |
| **2** | `seed.py` (idempotent) | get-or-create, permission catalog | Re-run twice, row counts unchanged |
| **3** | `security.py`: bcrypt + JWT | hashing vs signing, 72-byte rule, claims | You can explain why the access token has no roles |
| **4** | `get_current_user` + `/auth/me` | `HTTPBearer`, decode, 401 | No token → 401, garbage token → 401, valid → 200 |
| **5** | Register + login | mass assignment, generic errors, threadpool | `{"role":"admin"}` still creates a customer |
| **6** | Refresh table, cookie, rotation, logout | token state machine, hashing at rest, Origin check | Reuse of an old token kills the chain |
| **7** | `require_permission` factory | DB-resolved permissions, `selectinload` | Customer on staff route → 403; no token → 401 |
| **8** | Tickets service + routes | ownership predicate, IDOR, 404-not-403 | Customer B gets 404 for A's ticket |
| **9** | Admin API | role assignment, permission catalog endpoints | Role change visible on the very next request |
| **10** | Permission matrix + regressions | parametrized tests, dependency override | Full matrix green, and you can add a row in 5 minutes |
| **11** | React shell + auth context | context, in-memory token, bootstrap | Reload keeps you logged in via silent refresh |
| **12** | Dashboards + guards + inspector | Router layouts, single-flight refresh | Hidden button **and** 403 on manual call |

**If you only have 40 minutes today:** do the row you're on, run the proof, and stop. Every row
ends with a runnable app — that is constitution axiom 6, not a suggestion.

---

## 3. Deep dives

### 3.1 Async Python: the one thing that will bite you

FastAPI runs one event loop. `await` yields control while waiting on I/O. Anything CPU-bound
that you `await` naively still blocks that loop for its whole duration.

bcrypt at cost 12 is intentionally ~100 ms of CPU. Two users logging in simultaneously would
serialize. So:

```python
# app/core/security.py — sketch
from anyio import to_thread
from pwdlib import PasswordHash
from pwdlib.hashers.bcrypt import BcryptHasher

# PasswordHash.recommended() would choose Argon2 — we want bcrypt explicitly.
_hasher = PasswordHash((BcryptHasher(rounds=12),))

async def hash_password(raw: str) -> str:
    return await to_thread.run_sync(_hasher.hash, raw)

async def verify_password(raw: str, stored: str) -> bool:
    return await to_thread.run_sync(_hasher.verify, raw, stored)
```

**What to learn:** what "blocking the event loop" means physically (no other request progresses),
why `async def` around sync CPU work is *not* enough, and what a threadpool buys you.

**Byte vs character counting:** `"é"` is 1 character, 2 UTF-8 bytes. bcrypt's limit is 72
**bytes**, so a validator must do `len(raw.encode("utf-8")) > 72 → 422`.

### 3.2 FastAPI dependencies: why a closure, not a decorator

The guard is a function that returns a function. The outer call happens once at import time and
captures the code; the inner call happens per request.

```python
# app/api/deps.py — sketch
def require_permission(code: str):
    async def guard(user: User = Depends(get_current_user)) -> User:
        if code not in user.permission_codes:
            raise HTTPException(403, "Insufficient permissions")
        return user
    return guard
```

Learn: `Depends` caches a dependency within a request (so `get_current_user` runs once even if
three guards need it), why the guard **returns** the user, and why `get_current_user` owns 401
while the guard owns 403. One function, one failure mode — that separation is what makes the
permission matrix testable.

**Trap:** `HTTPBearer()` with the default `auto_error=True` raises **403** for a missing
Authorization header in FastAPI. Your spec requires 401. Use `auto_error=False`, inspect
`credentials`, and raise 401 yourself with a `WWW-Authenticate: Bearer` header.

### 3.3 SQLAlchemy async: sessions, loading, transactions

Three facts cover 90% of async SQLAlchemy pain:

1. **A session is a unit of work, not a connection.** One per request, closed by the dependency.
2. **Lazy loading does not work in async code.** Touching `user.roles` outside an `await` raises
   `MissingGreenlet`. You must `selectinload` at query time.
3. **`expire_on_commit=False`** stops SQLAlchemy from invalidating your objects after commit, so
   you can still serialize the response without a surprise round-trip (which would also raise
   `MissingGreenlet`).

```python
# permission resolution — sketch
stmt = (
    select(User)
    .where(User.id == user_id)
    .options(selectinload(User.roles).selectinload(Role.permissions))
)
```

Learn: `selectinload` vs `joinedload` (separate IN-query vs JOIN — `selectinload` is safer for
collections), `secondary=` association tables, and why `user.roles` is a list, not a single role.
The absence of `user.role` is the whole point: with many-to-many, a role is a set.

**Transaction boundary:** commit once at the end of a successful request; roll back on exception.
That is why refresh rotation and ticket creation can't leave half-written state.

**MySQL specifics you must know:** InnoDB for transactions/FKs, `utf8mb4` for emoji and non-Latin
text, UTC everywhere, and `RESTRICT` on `tickets.customer_id` so a user with tickets cannot be
deleted. `CASCADE` on join tables is safe because they're pure links.

### 3.4 JWT: signed, not secret

A JWT is three base64url segments: header, payload, signature. Anyone can read the payload with
`atob`. The signature only proves *nobody changed it* — it hides nothing.

```python
jwt.encode(
    {"sub": str(user.id), "iat": now, "exp": now + timedelta(minutes=15), "typ": "access"},
    settings.secret_key,
    algorithm="HS256",
)
```

Learn: HS256 is symmetric (same secret signs and verifies — fine for one backend); `sub` must be
a **string** per spec, so cast to `int` before querying; always pass `algorithms=["HS256"]` to
`decode` to prevent algorithm confusion; `exp` is enforced by PyJWT but you should also reject a
token whose `typ` isn't `"access"`.

**Why no roles in the token:** if permissions were claims, demoting an admin would leave them
powerful until expiry, and logout could not revoke an access token at all. 15 minutes is the
blast radius we accept; per-request DB resolution is what makes role changes instant.

### 3.5 Refresh rotation: the state machine

Draw this before you code it. A refresh token is a row, not a JWT.

```
states: active ──rotate──> revoked (replaced_by_id → new)
        active ──logout──> revoked
        revoked ──presented again──> REUSE DETECTED → revoke the whole descendant chain
        expired ──presented──> 401
```

Implementation facts to learn:

- Plaintext = `secrets.token_urlsafe(32)` (256 bits). Stored value = `sha256(plaintext)` hex.
  Compare by hashing the presented value and looking up the unique index — never store plaintext.
- The cookie is `httpOnly`, `SameSite=Lax`, `Path=/auth`, `Secure` in production, 7-day `maxAge`.
  `Path=/auth` means the browser only sends it to `/auth/*` — which is exactly why the refresh
  endpoint lives there.
- Rotation is **atomic**: mark old revoked, insert new with `replaced_by_id` set, set new cookie.
  A crash between steps must not leave two active tokens.
- **Reuse detection:** a presented token that exists but is already revoked means theft (or a buggy
  client). Revoke its whole replacement chain and force re-login.
- `Origin` must equal the configured frontend origin on refresh and logout, because cookies are
  auto-sent and `SameSite` alone is not a CSRF strategy.

### 3.6 RBAC data model and permission resolution

```
users ──< user_roles >── roles ──< role_permissions >── permissions
```

- `users` owns authentication. There is no `customers` table. Customer/staff/admin are rows in
  `roles`.
- A permission is a code like `ticket:read_all`. Roles are bundles of codes. The `admin` role
  holds **every** code explicitly — no `is_superuser` flag, no `if role == "admin"`.
- Resolution per request: `user → roles → permissions`, deduplicated into a set of codes.
- Adding a permission is a **data change plus one guard call**. It is never a route-body edit.

Learn to answer: *why does adding a fourth role require editing zero route files?* Because routes
ask "do you hold this code?", not "are you this role?".

### 3.7 401 / 403 / 404 and IDOR

| Situation | Status | Why |
|---|---|---|
| No token, malformed token, expired token | 401 | Identity is not established |
| Valid identity, missing permission | 403 | Identity is known; capability is not |
| Ticket doesn't exist **or** belongs to another customer | 404 | Distinguishing the two leaks existence |
| Permission + ownership OK | 2xx | — |

**IDOR** is the bug where `/tickets/42` works for anyone who guesses `42`. The fix is not a
Python comparison after fetching; it is folding ownership into the query:

```python
stmt = select(Ticket).where(Ticket.id == ticket_id, Ticket.customer_id == me.id)
ticket = (await session.execute(stmt)).scalar_one_or_none()
if ticket is None:
    raise HTTPException(404, "Ticket not found")
```

That single line gives you IDOR protection and correct 404 semantics simultaneously. For
`read_all` holders, drop the `customer_id` predicate — but keep the permission check. **`read_all`
bypasses ownership, never authorization.**

### 3.8 Mass assignment

The attack: `POST /auth/register {"email": ..., "password": ..., "role": "admin"}`.

The defense is structural, not a filter:

1. The register schema has only `email` and `password`. Pydantic v2 ignores unknown fields by
   default (`extra="ignore"`), so `role` never reaches the service.
2. The service hard-codes the `customer` role lookup.
3. A regression test asserts the created user's roles are exactly `["customer"]`.

Learn: "allowlist the input schema" beats "blocklist dangerous keys", because a blocklist is a
permanent maintenance burden and always misses one.

### 3.9 Testing the permission matrix

The matrix is not prose — it is a parametrized test.

```python
@pytest.mark.parametrize(("role", "method", "path", "expected"), [
    ("customer", "GET",  "/tickets",            200),
    ("customer", "GET",  "/tickets/all",        403),
    ("customer", "PATCH","/tickets/1/status",   403),
    ("staff",    "GET",  "/tickets/all",        200),
    ("staff",    "GET",  "/admin/users",        403),
    ("admin",    "GET",  "/admin/users",        200),
    ("anon",     "GET",  "/tickets",            401),
])
async def test_matrix(client_for, method, path, expected):
    ...
```

Concepts to learn:

- **Dependency override** to point `get_session` at the test schema.
- **Outer transaction + rollback** per test: open a connection, begin, bind the session to it, roll
  back in teardown. This is faster than truncating tables and gives perfect isolation.
- **Savepoints** (`begin_nested()`) for code paths that call `commit()` — otherwise the app's
  commit would end your outer transaction and leak data.
- **Real MySQL**, because SQLite would silently accept different FK and collation behavior.
- **Cookie inspection** for rotation: assert on `Set-Cookie` and replay the *old* value to prove
  reuse detection.
- **Expiry tests** without sleeping: mint a token with `exp` in the past, or freeze time.

### 3.10 React: the parts that are actually hard

The UI is not the lesson; the session lifecycle is.

**Bootstrap problem.** The access token lives in memory, so a page reload logs you out. On mount,
call `POST /auth/refresh` (cookie travels automatically), store the new access token, then
`GET /auth/me`. While that's in flight, guards must render a loading state — not redirect — or
you get a login-loop on every refresh.

**Single-flight refresh.** Three components fire requests, all get 401, all call `/auth/refresh`.
The first rotates the cookie; the other two present the now-revoked token and **trip reuse
detection**, logging the user out. Fix: one module-level promise that all callers await.

```ts
// src/api/client.ts — sketch
let refreshing: Promise<string> | null = null;
function refreshOnce() {
  refreshing ??= doRefresh().finally(() => { refreshing = null; });
  return refreshing;
}
```

**StrictMode double-effect.** In dev, React 19 runs effects twice. A naive bootstrap refresh fires
twice → same reuse trap. The single-flight promise fixes this too, but you should know *why* it
happened rather than just adding a ref.

**Guards are UX.** `RequirePermission` renders a 403 page or hides a button. It does not protect
anything. The Access Inspector exists to prove this: click the forbidden button, watch the API
return 403 even though the UI hid it.

**Decoding a JWT in the browser** is `atob` on the middle segment with base64url fixes
(`-`→`+`, `_`→`/`, re-pad). You are *displaying* claims, never trusting them — the client cannot
verify the signature and must not try.

### 3.11 Patterns: only after the pain

- **Guard dependency factory** is in M1 because the duplication is already real: every protected
  route needs the same two checks.
- **Strategy** waits for M3 because in M1 a single `if` on status transitions is fine. Refactor
  only when you can measure the payoff.
- **Factory** stays deferred: there is no role-specific object to create and no second hashing
  algorithm. Writing one now would be speculative generality.

Learn the boundary cold: **permission = "may you attempt this?"; strategy = "given that you may,
what are the rules?"** A policy that queries the DB to decide permission is a mislabeled guard.

### 3.12 Config and secrets

`pydantic-settings` reads `.env` into a typed object at import time. Missing `SECRET_KEY` should
crash the app, not silently default to `"changeme"`. `.env` is gitignored; `.env.example` holds
placeholders. No secret, token, or password hash ever reaches a log line — which means the logging
you add for debugging must redact request bodies on auth routes.

---

## 4. Traps, by symptom

| Symptom | Cause | Concept to revisit |
|---|---|---|
| `MissingGreenlet` | Touching a lazy relationship outside `await` | §3.3 `selectinload` |
| Missing header returns 403 instead of 401 | `HTTPBearer()` default `auto_error=True` | §3.2 |
| Role change doesn't take effect | Permissions cached or embedded in the JWT | §3.5 |
| Logged out randomly after several tabs/refreshes | Parallel refreshes + rotation reuse detection | §3.10 single-flight |
| Login-loop on page reload | Guard redirects before bootstrap refresh finishes | §3.10 |
| CORS error only on `PATCH` with `Authorization` | Preflight not allowed; wildcard used with credentials | §1.2 CORS |
| 422 on a long password instead of truncation | Correct! bcrypt limit enforced at validation | §3.1 |
| Foreign ticket returns 403 | Ownership checked in Python after fetch, or existence leaked | §3.7 |
| User with tickets can't be deleted — "bug" | `ON DELETE RESTRICT` doing its job | §3.3 |
| Test data leaks between tests | App `commit()` escaped the test transaction | §3.9 savepoints |
| Seed duplicates rows on second run | No get-or-create by unique key | §2 step 2 |
| Refresh works in Postman but not the browser | `SameSite`/`Path`/`credentials: "include"` mismatch | §1.4 cookies |
| `uv`/`npm` command not found | Use `py`, `uv`, and `npm.cmd` on this machine | tech-stack env notes |

---

## 5. Deliberately deferred (do not study yet)

| Topic | Why not yet |
|---|---|
| Alembic migrations | `create_all` is the M1 mechanism; migrations matter when schema churns |
| Docker / compose | Local MySQL service already exists; adds noise before RBAC lands |
| Redis, caching, rate limiting | No measured need; caching permissions per request is already enough |
| Argon2id | bcrypt is the chosen trade-off; know *why* it was chosen, not how to swap it |
| OAuth / OIDC / MFA | Out of scope; would obscure the identity pipeline |
| Multi-tenancy | Changes the ownership predicate from `customer_id` to `tenant_id`; later |
| TypeScript | Plain JS keeps the frontend small; types are a separate skill |
| WebSockets / background workers | No real-time or async-job requirement |
| Kubernetes / scaling | Non-goal in the mission |

---

## 6. Oral review (pass this before M1 exit)

Answer without notes. If you can't, that's the next thing to study.

**Identity & tokens**
1. Why does the access token contain no roles or permissions?
2. What exactly does the JWT signature prove — and what does it *not* hide?
3. Why is the refresh token opaque instead of a JWT?
4. Why store a SHA-256 hash of the refresh token instead of the token itself?
5. Why is the refresh cookie `Path=/auth` rather than `/`?

**Rotation**
6. Walk through what happens on a successful refresh, field by field.
7. A revoked token is presented. What do you do, and why not just return 401?
8. Why do refresh and logout need an `Origin` check when the cookie is `SameSite=Lax`?

**Authorization**
9. Give one concrete request for each of 401, 403, and 404.
10. Why is another customer's ticket a 404 instead of a 403?
11. Why is ownership a SQL predicate rather than a Python comparison?
12. `read_all` bypasses what — permission or ownership? Why?
13. Why does adding a fourth role require zero route edits?
14. Where is the only place in the codebase a permission code is checked?

**Passwords & input**
15. Why must bcrypt work run in a threadpool?
16. Why reject a 73-byte password instead of truncating it?
17. How does the register schema stop `{"role": "admin"}`?

**Data & async**
18. What raises `MissingGreenlet`, and what are the two fixes?
19. Why `expire_on_commit=False`?
20. What does `ON DELETE RESTRICT` on `tickets.customer_id` protect?

**Testing & frontend**
21. How does the permission matrix stay executable rather than a document?
22. Why do tests run against real MySQL and a separate schema?
23. Why does the frontend need single-flight refresh?
24. Why is a route guard not a security control?
25. Permission vs policy: state the difference in one sentence.

---

## 7. Drills (do these, don't just read them)

1. **Draw the ERD** from memory, including FK actions and unique constraints. Compare to models.
2. **Draw the refresh state machine** (active / revoked / expired / reuse). Then write the test
   for each arrow before the implementation.
3. **Implement `require_permission` from a blank file**, with two tests proving 401 vs 403. Done
   when `grep -r "admin" app/api/routes/` returns nothing.
4. **Break it on purpose:** remove the `customer_id` predicate from the ticket read and watch the
   IDOR test fail. Restore it. That failure is the lesson.
5. **Add a permission end-to-end in under 15 minutes:** insert the code in the catalog, attach it
   to a role in the seed, add the guard to a route, add one matrix row. No route-body branching.
6. **Trip reuse detection** by hand in Swagger: refresh twice with the first cookie, then replay
   it. Observe the chain revoke.
7. **Mass-assignment probe:** register with `role: "admin"`, then `GET /auth/me`.
8. **Trace one request** through all four pipeline stages, naming the file and function at each.

---

## 8. Glossary

| Term | Meaning in this project |
|---|---|
| **Identity** | The authenticated user, proven by a valid access token |
| **Permission** | A code (`ticket:read_all`) granting the *capability* to attempt an action |
| **Role** | A named bundle of permissions; contains no logic |
| **Ownership** | The rule that a resource belongs to a specific customer |
| **IDOR** | Attack where a user changes an id in the URL to reach someone else's resource |
| **Access token** | 15-min HS256 JWT, memory-only, carries only `sub`/`iat`/`exp`/`typ` |
| **Refresh token** | 7-day opaque random string, hashed in DB, delivered as an httpOnly cookie |
| **Rotation** | Every refresh revokes the presented token and issues a replacement |
| **Reuse detection** | Presenting an already-rotated token revokes the entire descendant chain |
| **Mass assignment** | Client sending extra fields (e.g. `role`) to influence server-side creation |
| **Permission matrix** | Parametrized test asserting role × endpoint → expected status |
| **Guard** | The `require_permission` dependency; owns 403 |
| **Policy** | A pure business rule applied *after* permission passes (M3) |
| **Fail closed** | Unknown/absent case denies rather than allows |
| **Single-flight** | Deduplicating concurrent identical async operations into one promise |

---

**The bar for "learned":** you can rebuild the auth + authorization core from a blank file, explain
each 401/403/404 with a real request, and add a permission without touching a route body. Everything
else in this file is scaffolding for those three abilities.
