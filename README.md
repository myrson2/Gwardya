# Gwardya

> A learning-first support-ticket app that enforces real role-based access control — one
> identity, data-driven roles and permissions, ownership-aware reads, and revocable JWT sessions.

**Status:** Specifications ratified (v1.1) · Development starts at Milestone 0 · No application
code yet.

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
  backend/                # planned (M0–M1)
    app/
      api/                # routers + permission dependencies
      core/               # config, security, permission catalog
      db/                 # engine, session, base, seed
      models/             # SQLAlchemy models
      schemas/            # Pydantic I/O
      services/           # business rules + ownership predicates
  frontend/               # planned (M2)
    src/
      api/                # fetch wrapper + refresh-on-401
      auth/               # token memory, guards
      pages/              # customer / staff / admin dashboards
```

## Getting started

> Not runnable yet — M0 will add the backend scaffold, `.env.example`, and `db/setup.sql`.

Prerequisites already verified on the development machine:

- Python **3.14.5** via the `py` launcher (plus `uv` 0.12.9)
- Node **24** / npm **11** (use `npm.cmd`; the `.ps1` wrapper is blocked by execution policy)
- MySQL **8.0**, service `MySQL80`, running locally

Planned local flow:

```powershell
# 1. Create the database and dedicated app user (run once, as root)
& "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe" -u root -p `
  -e "source backend/db/setup.sql"

# 2. Backend
cd backend
uv sync
uv run uvicorn app.main:app --reload

# 3. Frontend (new terminal)
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

## Roadmap

| Phase | Theme | Exit gate |
|---|---|---|
| **M1** | Backend RBAC core | All endpoints work; permission-matrix and IDOR tests pass |
| **M2** | Frontend + Access Inspector | Three dashboards, guards, visible 403s |
| **M3** | Hardening + graduation | Reuse detection, Pattern Lab, replies added unaided |

Estimated pace: **≈40–42 sessions of ~40 minutes**, about **7–9 weeks** at under 4 hours/week.

## Non-goals

Ticket replies (until M3), attachments, email verification, password reset, OAuth/MFA,
multi-tenancy, Docker, Alembic, Redis/caching, microservices, WebSockets.

## License

Personal learning project. License TBD.
