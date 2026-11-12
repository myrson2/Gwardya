# Tech Stack — RBAC Learning Project

Versions are pinned by `backend/uv.lock` and `frontend/package-lock.json`. The table lists the
version families verified on this machine.

## Core Stack Matrix

| Layer | Technology | Version | Rationale |
|---|---|---|---|
| Language (backend) | Python | 3.14.x (uv-managed, WSL2) | Async stack has cp314 wheels |
| Package manager | uv | 0.13.x | Fast, lockfile-based, already installed |
| API framework | FastAPI | latest stable, pinned | Async-native; dependency injection fits permission gates |
| ASGI server | Uvicorn | latest stable, pinned | Standard local runner |
| ORM | SQLAlchemy | 2.0.x (async) | `AsyncSession`, explicit loading, typed models |
| DB driver | asyncmy | 0.2.x | Async MySQL; Linux (cp314) wheels used |
| Database | MySQL | 8.0 (inside WSL2) | Realistic SQL; isolated from Windows `MySQL80` |
| Validation | Pydantic / pydantic-settings | 2.x | Request/response schemas, typed config |
| JWT | PyJWT | 2.x | Maintained, minimal, HS256 |
| Password hashing | pwdlib[bcrypt] | 0.3.x | Maintained wrapper; bcrypt algorithm (cost 12) |
| Frontend | React + Vite | React 19.x / Vite 7.x | Fast dev loop; plain JS, no TypeScript |
| Routing | React Router | 7.x | Route guards and layouts |
| HTTP client | native `fetch` | n/a | No extra dependency; `credentials: "include"` |
| Tests | pytest + pytest-asyncio + httpx | latest stable, pinned | Async API tests against real MySQL |
| Lint/format | ruff | latest stable | One tool for both |

**Password-hashing trade-off:** bcrypt is battle-tested and widely deployed, but it is not
memory-hard like Argon2id and has a hard 72-byte input limit. The limit is enforced at
validation, never silently truncated.

**Environment notes**

- The backend runs inside **WSL2 (Ubuntu 24.04)**. Run every `uv`/`pytest`/`uvicorn` command
  there, never from Windows PowerShell — Windows Smart App Control blocks unsigned
  `pydantic_core`/`asyncmy` binaries, and a Windows `uv run` would rebuild `.venv` as a Windows venv.
- Python is uv-managed in WSL (3.14.x). `uv` lives at `~/.local/bin/uv`.
- MySQL 8 runs inside WSL as systemd service `mysql`, bound to `127.0.0.1:3307`.
  Port 3307 (not 3306) because WSL uses mirrored networking and Windows `MySQL80` owns 3306/33060.
- WSL reaches Windows-shared loopback over IPv4 only: browse the API at
  `http://127.0.0.1:8001`, **not** `http://localhost:8001` (Windows resolves `localhost` to `::1`).
- MySQL is forced to UTC (`default-time-zone = "+00:00"`).
- Frontend commands run on Windows; `npm.ps1` is blocked by execution policy, so use `npm.cmd`.

## Layer Boundaries

**Backend**

1. **API / routers** (`app/api/routes/`) — HTTP concerns only: status codes, request/response
   schemas, dependency wiring. No SQL, no business rules.
2. **Dependencies** (`app/api/deps.py`) — identity resolution (`get_current_user`) and
   authorization gates (`require_permission`). The only place permission codes are checked.
3. **Services** (`app/services/`) — business rules and ownership predicates; receives an
   `AsyncSession` and the authenticated user.
4. **Persistence** (`app/db/`, `app/models/`) — engine, session factory, ORM models, queries.
5. **Schemas** (`app/schemas/`) — Pydantic I/O contracts; never expose `hashed_password` or
   token hashes.

**Frontend**

1. **API client** (`src/api/`) — fetch wrapper, attaches access token, handles 401 → refresh once.
2. **Auth context** (`src/auth/`) — in-memory access token, current user, permissions,
   login/logout.
3. **Guards** (`RequireAuth`, `RequirePermission`) — UX routing only.
4. **Pages** — customer, staff, admin dashboards + Access Inspector.

## Design Patterns

Patterns are vocabulary for recurring problems, not a checklist. A pattern enters the codebase
only when a present duplication or variation demands it (Constitution axiom 8). Full rationale,
code sketches, and exercises live in `specs/design-patterns.md`.

| Pattern | Status | Where | Rule |
|---|---|---|---|
| Guard dependency factory | **M1-3** | `require_permission(code)` | Permission-based, DB-resolved; never role-name checks |
| Strategy | **M3 Pattern Lab** | `TicketAccessPolicy` / `StatusTransitionPolicy` | Pure, explicit mapping, unknown role denies |
| Factory Method / Simple Factory | **Deferred** | Role-specific profiles or multi-algorithm hashing | Only when the variation exists; name it precisely |
| GoF Decorator | **Not used** | — | FastAPI dependencies cover the wrapping need; don't mislabel |

**Boundary:** permissions answer *may you attempt this?*; strategies answer *given that you may,
what are the rules?* Strategy never replaces the permission guard.

## Rejected Alternatives & Forbidden Patterns

| Rejected | Why |
|---|---|
| Separate `customers`/`staff`/`admins` tables | Triplicates auth; breaks "one identity, many roles" |
| Role-string checks in route bodies | Couples code to data; defeats the permission catalog |
| `is_superuser` bypass | Hides the authorization path; admin becomes magic |
| Permissions embedded in the access JWT | Stale grants after demotion; revocation impossible until expiry |
| Access token in `localStorage` | XSS-readable; we use memory + httpOnly refresh |
| Stateless refresh JWT | Cannot revoke on logout |
| `passlib` (any algorithm) | Unmaintained; breaks with modern bcrypt releases |
| Sync SQLAlchemy / blocking DB calls | Blocks the event loop under async FastAPI |
| Lazy relationship loading | Raises `MissingGreenlet` in async code |
| 403 for another user's resource | Leaks existence; use 404 |
| Pattern-first architecture (Factory/Strategy before a real variation exists) | Speculative generality; obscures the RBAC lesson |
| Docker / Alembic / Redis / microservices / OAuth / email / replies / multi-tenancy | Out of M1 scope; adds noise before the RBAC lesson lands |

## Architecture (request path)

```
React page
  → fetch (Bearer access token)
    → FastAPI router
      → get_current_user (decode JWT, load user)
      → require_permission("ticket:read_all")
        → AsyncSession query: user → roles → permissions
      → service (ownership predicate if read_own)
        → SQLAlchemy SELECT ... WHERE customer_id = :me
      → Pydantic response
```
