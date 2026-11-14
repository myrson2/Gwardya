# Project Context — Gwardya

> Working notes for picking this project back up. Complements the ratified specs in `specs/`
> (source of truth) and the learning guide in `concepts.md`. This file records **what the
> environment and code actually look like right now**, including the non-obvious gotchas.

Last updated: 2026-11-14 · **Backend M1 built; M1-3 is the student exercise.** The detailed
inventory lives in [`docs/BOILERPLATE.md`](docs/BOILERPLATE.md), the exercise brief in
[`docs/M1-3-authorization-task.md`](docs/M1-3-authorization-task.md).

---

## 1. Where things stand

| Area | State |
|---|---|
| Specs | Ratified v1.1 (`specs/`) — not modified except environment notes in `tech-stack.md` |
| Backend M1-0 | Done: config, async engine/session, app, health routes |
| Backend M1-1 | Done: 7 tables, naming convention, FKs/cascades, catalog, idempotent seed |
| Backend M1-2a/2b | Done: bcrypt, identity-only JWT, refresh rotation/reuse, logout, Origin check |
| Backend M1-3 | **Student exercise:** `require_permission`, `require_any_permission`, `scope_tickets` are `NotImplementedError` stubs |
| Backend M1-4 / M1-5 | Done: ticket routes/status policy, admin routes/role assignment |
| Database | MySQL 8.0.46 inside WSL2, UTC, two schemas, least-privilege app user |
| API | Boots and serves `/docs`; protected routes return 500 until M1-3 is implemented |
| Quality gates | `ruff check .` clean; `pytest -q` → 32 passed, 18 skipped (M1-3 suite) |
| Frontend | Not started (M2) |
| Git | Last commit `dad7c3d`; the M1-2..M1-5 implementation and `docs/` are uncommitted |

M1-0/M1-1/M1-2 exit criteria are met. M1-4 and M1-5 are implemented but their acceptance
depends on M1-3: until the guards exist, every protected route raises `NotImplementedError`.

---

## 2. Runtime architecture

```
Windows 11 host
├── MySQL80 (Windows service)        127.0.0.1:3306   ← untouched, unrelated
├── postgres                         0.0.0.0:8000     ← why the API is on 8001
│
└── WSL2 (Ubuntu 24.04, mirrored networking, systemd)
    ├── mysql (systemd service)      127.0.0.1:3307   ← project database
    └── uvicorn (FastAPI)            0.0.0.0:8001     ← API
```

The backend **must** run inside WSL. Windows-native execution is blocked by Smart App Control.

### Ports and why they are unusual

| Port | Owner | Reason |
|---|---|---|
| 3306 | Windows `MySQL80` | Default Windows MySQL install; left running for other work |
| 3307 | WSL `mysql` | Mirrored networking shares the port space, so WSL MySQL cannot bind 3306 |
| 33061 | WSL MySQL X plugin | Same conflict as above (Windows uses 33060) |
| 8000 | Windows `postgres` (pid varies) | Mirrored networking blocks WSL from binding 8000 |
| 8001 | WSL `uvicorn` | Chosen to avoid the postgres clash |

### Access from Windows

Use **`http://127.0.0.1:8001`**, not `http://localhost:8001`.

- WSL mirrored networking shares the host's **IPv4** loopback but **not** IPv6.
- Windows resolves `localhost` to `::1` first, which black-holes (no RST), so requests hang.
- Verified: `127.0.0.1:8001` works; `localhost:8001` times out; WSL's own `::1` is unreachable from Windows.

---

## 3. Environment details

| Component | Version / setting |
|---|---|
| WSL distro | `Ubuntu-24.04`, user `merss` (uid 1000, NOPASSWD sudo) |
| WSL config | `C:\Users\merss\.wslconfig` — 3 GB RAM, 2 GB swap, `networkingMode=mirrored` |
| `/etc/wsl.conf` | `[boot] systemd=true`, `[user] default=merss` |
| Python | 3.14.10, uv-managed (`~/.local/share/uv/python/...`) |
| uv | 0.13.7 (`~/.local/bin/uv`) |
| MySQL | 8.0.46 (`mysql-server`), systemd-managed, auto-starts with WSL |
| MySQL time zone | `default-time-zone = "+00:00"` in `/etc/mysql/mysql.conf.d/mysqld.cnf` |
| MySQL port | `port = 3307`, `mysqlx-port = 33061` in the same file |
| Databases | `rbac_learning`, `rbac_learning_test` (`utf8mb4` / `utf8mb4_0900_ai_ci`) |
| DB user | `rbac_app`@`localhost` and `rbac_app`@`127.0.0.1` |
| DB grants | SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, INDEX, ALTER, REFERENCES on both schemas only |

Python packages: 42 runtime+dev packages, `uv sync --check` reports no changes.
Notable pins: FastAPI 0.162.5, SQLAlchemy 2.0.57, asyncmy 0.2.18, Pydantic 2.14.3,
PyJWT 2.15.1, pwdlib 0.3.1, bcrypt 5.0.0 (cost 12), cryptography 50.0.2, uvicorn 0.54.0.

---

## 4. Files created

```
RBAC-PROJECT/
├── .gitignore                     # .venv, .env, __pycache__, caches, node_modules
├── README.md                      # status, WSL workflow, updated layout
├── concepts.md                    # learning guide derived from specs
├── context.md                     # this file
├── docs/                          # boilerplate inventory + M1-3 exercise brief
├── specs/                         # ratified specs (tech-stack env notes updated)
└── backend/
    ├── .env                       # real secrets — GITIGNORED, never commit
    ├── .env.example               # placeholders only (tracked)
    ├── .python-version            # 3.14
    ├── pyproject.toml             # deps, dev group, ruff/pytest config, package = false
    ├── requirements.txt           # pip fallback
    ├── uv.lock
    ├── app/
    │   ├── main.py                # app, CORS, lifespan create_all, AppError handler, health
    │   ├── core/                  # config, enums, catalog, security
    │   ├── db/                    # base (naming convention), session, seed
    │   ├── models/                # user, role, permission, ticket, refresh_token, associations
    │   ├── schemas/               # auth, ticket, admin
    │   ├── services/              # auth, ticket, admin, errors, ticket_scope (M1-3 stub)
    │   └── api/
    │       ├── deps.py            # get_current_user, verify_origin + M1-3 guard stubs
    │       └── routes/            # auth.py, tickets.py, admin.py
    ├── db/
    │   ├── setup.sql              # databases, users, grants (password placeholder)
    │   └── setup.sh               # injects password from .env, applies SQL
    └── tests/
        ├── conftest.py            # session engine, rollback fixture, client + login helper
        ├── test_health.py
        ├── test_schema.py         # V-01..V-09
        ├── test_seed.py           # V-10..V-19
        ├── test_auth.py           # M1-2a/2b
        └── test_authorization.py  # M1-3 acceptance matrix (skipped by default)
```

`backend/.venv` is a **Linux** venv (`bin/`, no `Scripts/`). Do not run Windows `uv` against it.

The old layout (`app/model/`, `app/core/enum.py`, `backend/app.py`) has been removed. The only
intentionally unfinished code is the M1-3 exercise:

- `app/api/deps.py` → `require_permission`, `require_any_permission` (raise `NotImplementedError`)
- `app/services/ticket_scope.py` → `scope_tickets` (raises `NotImplementedError`)

Everything else imports, boots, seeds, and passes its tests.

---

## 5. Key decisions and why

1. **WSL2 instead of Windows-native.** Smart App Control (`VerifiedAndReputablePolicyState=1`)
   blocks unsigned `_pydantic_core.pyd` and `asyncmy/protocol.pyd`. Disabling it is one-way and
   machine-wide; WSL costs ~1 GB RAM only while running.
2. **uv project lives in `backend/`**, not repo root (matches `backend/uv.lock` in specs);
   `[tool.uv] package = false` so the app runs from source.
3. **SQLAlchemy pinned to 2.0.x (2.0.57)**, not 2.1.x, per ratified tech-stack.
4. **`cryptography` added.** asyncmy cannot complete MySQL 8's `caching_sha2_password` handshake
   over TCP without it. Comment in `pyproject.toml` explains this.
5. **MySQL inside WSL**, not Windows. Avoids firewall/NAT/grant-host problems and keeps the
   project database isolated from the pre-existing Windows `MySQL80`.
6. **MySQL forced to UTC** so `TIMESTAMP`/`DATETIME` semantics match Constitution §3.
7. **Mirrored networking** because NAT-mode `localhost` forwarding was broken on this build.
   Trade-off: shared ports forced API → 8001 and MySQL → 3307.
8. **IPv4-only binds.** asyncio sets `IPV6_V6ONLY` on IPv6 sockets, and Windows cannot reach
   WSL's IPv6 loopback in mirrored mode. So bind `0.0.0.0` and use `127.0.0.1`.
9. **Secrets never in git.** `.env` generated with random 32-byte `SECRET_KEY` and 24-byte DB
   password; verified ignored via `git check-ignore -v backend/.env`.

---

## 6. Daily workflow

```powershell
# Windows PowerShell → enter WSL
wsl -d Ubuntu-24.04
```

```bash
# Inside WSL
cd /mnt/c/Users/merss/Documents/RBAC-PROJECT/backend

uv sync                                  # only when deps change
uv run uvicorn app.main:app --reload --port 8001
```

Open `http://127.0.0.1:8001/docs`.

Checks:

```bash
uv run ruff check .
uv run pytest -q
```

One-time database bootstrap (already done; safe to re-run):

```bash
bash db/setup.sh
```

If WSL/MySQL ever misbehaves after a Windows restart:

```powershell
wsl --shutdown
wsl -d Ubuntu-24.04 --exec systemctl is-active mysql
```

> `/mnt/c` is slow (9p filesystem): first import/startup takes ~5–15 s. That is expected.

---

## 7. Verification evidence (M1-0 … M1-5)

| Check | Result |
|---|---|
| `ruff check .` | All checks passed |
| `pytest -q` | **32 passed, 18 skipped** (the skipped 18 are the M1-3 suite) |
| `test_schema.py` | 9 passed — 7 tables, CHECK, RESTRICT/CASCADE/SET NULL, no superuser |
| `test_seed.py` | 10 passed — counts (3/7/11/4/4), exact matrix, idempotency, bcrypt 12 |
| `test_auth.py` | 12 passed — register/login/me, cookie flags, rotation, reuse, logout, Origin, mass assignment |
| Seed run 1 | 7 permissions, 3 roles, 11 grants, 4 users, 4 tickets |
| Seed run 2 | all zeros (idempotent) |
| `GET /health` | `{"status":"ok"}` [200] |
| `GET /health/db` | `{"status":"ok","database":"mysql"}` [200] |
| `GET /docs` | 200 |
| `GET /auth/me` | 200 with `roles:["customer"]`, `permissions:["ticket:create","ticket:read_own"]` |
| `GET /tickets` no token | 401 |
| `GET /tickets` with token | 500 — expected until M1-3 guards are implemented |
| MySQL connection | `mysql 8.0.46`, `rbac_learning`, `utf8mb4_0900_ai_ci`, `time_zone=+00:00` |
| bcrypt | `BcryptHasher().rounds == 12` |

---

## 8. Next up — M1-3 (the exercise)

Only the authorization core remains. Read
[`docs/M1-3-authorization-task.md`](docs/M1-3-authorization-task.md), then implement:

1. `app/api/deps.py` → `require_permission(code)` and `require_any_permission(*codes)`.
   - membership in `user.permission_codes`; success returns the same `User`; failure is 403.
   - never use `role_names`, never decode the token again, never import the catalog.
2. `app/services/ticket_scope.py` → `scope_tickets(stmt, user)`.
   - `ticket:read_all` → statement unchanged.
   - otherwise add a SQL predicate `tickets.customer_id == user.id`, preserving existing where
     clauses.

Then:

```bash
RUN_M1_3=1 uv run pytest tests/test_authorization.py -q
uv run pytest -q
uv run ruff check .
```

The grader covers the full matrix, 401/403/404 semantics, IDOR indistinguishability, ownership
scoping in SQL, and role changes taking effect without re-login. Do not edit routes, services,
schemas, or tests to make it pass.

After M1-3 is green, the backend RBAC vertical slice is complete. The next milestone is M2
(frontend + Access Inspector).

---

## 9. Gotcha cheat sheet

| Symptom | Cause | Fix |
|---|---|---|
| `Seed failed (ProgrammingError)` on a fresh database | `seed.py` does not create tables; `create_all` runs in the app lifespan | Boot the API once, then run the seed |
| MySQL reports a CHECK violation as `OperationalError` (3819), not `IntegrityError` | SQLAlchemy does not map MySQL error 3819 | Catch `DBAPIError` in tests (as `test_schema.py` does) |
| `MissingGreenlet` after `expire_all()` + attribute access | Expired ORM objects lazy-refresh outside the async greenlet | Use `expunge_all()` and re-select, or `await session.refresh(obj)` |
| Assigning to a collection raises `InvalidRequestError` (lazy="raise") | The relationship was never eager-loaded | Re-select with `selectinload(...)` before assigning |
| `created_at`/`updated_at` are missing after `flush()` | Server defaults are not populated until read | `await session.refresh(obj)` after flush |
| `localhost:8001` hangs, `127.0.0.1` works | Windows prefers `::1`; WSL IPv6 loopback not shared | Use `127.0.0.1` |
| MySQL stuck `activating`, log says port 3306 in use | Windows `MySQL80` owns 3306 under mirrored networking | WSL MySQL stays on 3307 |
| `Address already in use` on 8000 | Windows `postgres` | Use 8001 |
| `Access denied ... using password: YES` right after WSL boot | MySQL still starting | Wait for `systemctl is-active mysql` |
| `_pydantic_core.pyd` / `asyncmy` blocked | Smart App Control on Windows | Run inside WSL |
| `uv run` wants to rebuild `.venv` | Running uv from Windows | Run uv inside WSL |
| `set: pipefail: invalid option name` | Script saved with CRLF | Save shell scripts with LF |
