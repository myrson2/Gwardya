# Gwardya

> A learning-first support-ticket app that enforces real role-based access control — one
> identity, data-driven roles and permissions, ownership-aware reads, and revocable JWT sessions.

**Status:** Specifications ratified (v1.1) · **Backend M1 built** — models, seed, auth, tickets,
admin routes, and the real-MySQL test suite are in place. **M1-3, the authorization core, is
the exercise:** implement `require_permission`, `require_any_permission`, and `scope_tickets`.

> **Start here:** [docs/M1-3-authorization-task.md](docs/M1-3-authorization-task.md) is the
> exercise. [docs/BOILERPLATE.md](docs/BOILERPLATE.md) documents everything already built.

---

## Why this exists

Most RBAC tutorials stop at `if user.role == "admin"`. That skips the parts that actually break
in real systems:

- ownership rules — a customer must not read another customer's ticket;
- stale authorization — roles baked into long-lived JWTs;
- refresh-token revocation and reuse;
- mass assignment — a client registering itself as admin;
- the difference between **401**, **403**, and **404**.

TicketGuard builds the whole vertical slice — MySQL schema, async FastAPI, JWT + rotating refresh
tokens, React UI, and an executable permission matrix — so the pattern is learned by shipping it,
not by reading about it.

## What the app does

| Role | Can do |
|---|---|
| **Customer** | Register, create tickets, read **only their own** tickets |
| **Staff** | Read **all** tickets, move status `open → in_progress → closed` |
| **Admin** | Everything staff can do, plus list users and assign roles |

The frontend hides what you cannot do. The backend is what actually says no.

## RBAC at a glance

```
users ──< user_roles >── roles ──< role_permissions >── permissions
```

| Permission | customer | staff | admin |
|---|:---:|:---:|:---:|
| `ticket:create` | ✅ | | ✅ |
| `ticket:read_own` | ✅ | | ✅ |
| `ticket:read_all` | | ✅ | ✅ |
| `ticket:update_status` | | ✅ | ✅ |
| `user:read` | | | ✅ |
| `user:assign_role` | | | ✅ |
| `role:read` | | | ✅ |

- **One** `users` table. Customer/staff/admin are roles, not separate tables.
- Permissions are **resolved from MySQL on every request**; the access token carries only `sub`.
- `admin` holds every permission explicitly — there is no superuser bypass.
- A missing permission is **403**. Another customer's ticket is **404**. No token is **401**.

## Tech stack

| Layer | Choice |
|---|---|
| API | FastAPI + Uvicorn |
| ORM / DB | SQLAlchemy 2.x async (`AsyncSession`) + MySQL 8 via `asyncmy` |
| Auth | PyJWT (15-min access) + rotating refresh cookie (7 days) |
| Passwords | bcrypt via `pwdlib` (cost 12, threadpooled) |
| Frontend | React + Vite (plain JS), React Router |
| Tests | pytest + pytest-asyncio + httpx against a real MySQL test schema |

## Repository layout

```
RBAC-PROJECT/
  specs/                  # ratified specifications (source of truth)
    constitution.md
    mission.md
    tech-stack.md
    roadmap.md
    design-patterns.md
  backend/                # M1 backend (M1-3 exercise outstanding)
    app/
      core/               # config, security, enums, permission catalog
      db/                 # engine, session, base, seed
      api/                # routers + guards (M1-3 stubs live in deps.py)
      models/             # SQLAlchemy models
      schemas/            # Pydantic I/O
      services/           # business rules + ownership predicate (M1-3 stub)
    db/                   # setup.sql / setup.sh (databases + least-privilege user)
    tests/                # real-MySQL suite; test_authorization.py grades M1-3
  docs/                   # boilerplate inventory + M1-3 task
  frontend/               # planned (M2)
    src/
      api/                # fetch wrapper + refresh-on-401
      auth/               # token memory, guards
      pages/              # customer / staff / admin dashboards
```

## Getting started

The backend runs inside **WSL2 (Ubuntu 24.04)**. Do not run backend commands from Windows
PowerShell: Smart App Control blocks unsigned `pydantic_core`/`asyncmy` binaries, and a Windows
`uv run` would rebuild `.venv` as a Windows venv.

Verified environment:

- WSL2 Ubuntu 24.04, user `merss`, systemd enabled
- Python **3.14.x** (uv-managed) and `uv` **0.13.x** inside WSL
- MySQL **8.0** inside WSL on `127.0.0.1:3307` (Windows `MySQL80` keeps 3306)
- Node **24** / npm **11** on Windows (use `npm.cmd`; the `.ps1` wrapper is blocked)

Local flow:

```bash
# 1. Enter WSL (one-time: uv + MySQL are already installed)
wsl -d Ubuntu-24.04
cd /mnt/c/Users/merss/Documents/RBAC-PROJECT/backend

# 2. Create the databases and dedicated app user (run once; needs sudo)
bash db/setup.sh

# 3. Install dependencies
uv sync

# 4. Run the API (the lifespan creates any missing tables)
uv run uvicorn app.main:app --reload --port 8001

# 5. First seed — second WSL terminal, once the API has booted
#    (idempotent; refuses APP_ENV=production)
uv run python -m app.db.seed
```

The seed talks to existing tables, so it must run after the app has created them once.

Then open **http://127.0.0.1:8001/docs** from Windows. Use `127.0.0.1`, not `localhost` —
Windows resolves `localhost` to IPv6 `::1`, which is not shared with WSL in mirrored mode.

Checks:

```bash
uv run ruff check .
uv run pytest -q                                   # 32 passed, 18 skipped
RUN_M1_3=1 uv run pytest tests/test_authorization.py -q
```

Frontend (new terminal, on Windows):

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

## Documentation

| Document | What it covers |
|---|---|
| [specs/constitution.md](specs/constitution.md) | Non-negotiable security, data, and testing invariants |
| [specs/mission.md](specs/mission.md) | Problem, personas, success metrics |
| [specs/tech-stack.md](specs/tech-stack.md) | Stack matrix, layer boundaries, rejected alternatives |
| [specs/roadmap.md](specs/roadmap.md) | M1–M3 milestones and exit criteria |
| [specs/design-patterns.md](specs/design-patterns.md) | When (and when not) to use Factory, Strategy, guards |
| [docs/BOILERPLATE.md](docs/BOILERPLATE.md) | What is built: layers, file map, request flow, invariants, deviations |
| [docs/M1-3-authorization-task.md](docs/M1-3-authorization-task.md) | The exercise: contracts, 401/403/404 rules, hints, acceptance checklist |

## Roadmap

| Phase | Theme | Exit gate |
|---|---|---|
| **M1** | Backend RBAC core | Built end to end; only M1-3 is yours. Gate: permission-matrix and IDOR tests pass |
| **M2** | Frontend + Access Inspector | Three dashboards, guards, visible 403s |
| **M3** | Hardening + graduation | Reuse detection, Pattern Lab, replies added unaided |

Estimated pace: **≈40–42 sessions of ~40 minutes**, about **7–9 weeks** at under 4 hours/week.

## Non-goals

Ticket replies (until M3), attachments, email verification, password reset, OAuth/MFA,
multi-tenancy, Docker, Alembic, Redis/caching, microservices, WebSockets.

## License

Personal learning project. License TBD.
