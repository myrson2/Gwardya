# Project Context — Gwardya

> Working notes for picking this project back up. Complements the ratified specs in `specs/`
> (source of truth) and the learning guide in `concepts.md`. This file records **what the
> environment and code actually look like right now**, including the non-obvious gotchas.

Last updated: 2026-11-12 · Milestone **M1-0 complete** (scaffold boots against real MySQL).

---

## 1. Where things stand

| Area | State |
|---|---|
| Specs | Ratified v1.1 (`specs/`) — not modified except environment notes in `tech-stack.md` |
| Backend scaffold | Done: config, async engine/session, FastAPI app, health routes, one test |
| Database | MySQL 8.0.46 inside WSL2, UTC, two schemas, least-privilege app user |
| API verified | `/health` → ok, `/health/db` → ok (real MySQL), `/docs` → 200 |
| Quality gates | `ruff check .` clean, `pytest -q` → 1 passed |
| Frontend | Not started (M2) |
| Git | **Nothing committed yet** — `.gitignore`, `backend/`, `concepts.md`, `context.md` untracked |

M1-0 exit criteria are met: the app boots and `/health/db` proves a live database round-trip.

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
├── specs/                         # ratified specs (tech-stack env notes updated)
└── backend/
    ├── .env                       # real secrets — GITIGNORED, never commit
    ├── .env.example               # placeholders only (tracked)
    ├── .python-version            # 3.14
    ├── pyproject.toml             # deps, dev group, ruff/pytest config, package = false
    ├── requirements.txt           # pip fallback, kept in sync with pyproject
    ├── uv.lock                    # 44 packages
    ├── app/
    │   ├── __init__.py
    │   ├── main.py                # FastAPI app, CORS, lifespan, /health, /health/db
    │   ├── core/
    │   │   ├── __init__.py
    │   │   └── config.py          # pydantic-settings, fails fast without SECRET_KEY
    │   └── db/
    │       ├── __init__.py
    │       ├── base.py            # DeclarativeBase
    │       └── session.py         # async engine + get_session (commit/rollback)
    ├── db/
    │   ├── setup.sql              # databases, users, grants (password placeholder)
    │   └── setup.sh               # injects password from .env, applies SQL
    └── tests/
        └── test_health.py         # ASGI smoke test for /health
```

`backend/.venv` is a **Linux** venv (`bin/`, no `Scripts/`). Do not run Windows `uv` against it.

Cleanup candidate: `backend/app.py` is a leftover `uv init` stub (`print('Hello World')`) and
can be deleted — it is not imported anywhere.

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

## 7. Verification evidence (M1-0)

| Check | Result |
|---|---|
| `uv sync --check` | up to date, 42 packages |
| `uv lock --check` | lockfile up to date |
| `ruff check .` | All checks passed |
| `pytest -q` | 1 passed |
| `GET /health` | `{"status":"ok"}` |
| `GET /health/db` | `{"status":"ok","database":"mysql"}` |
| `GET /docs` | 200 |
| Windows → WSL | `127.0.0.1:8001` returns 200 for all three routes |
| MySQL connection | `mysql 8.0.46`, `rbac_learning`, `utf8mb4_0900_ai_ci`, `time_zone=+00:00` |
| bcrypt | `BcryptHasher().rounds == 12` |

---

## 8. Next up — M1-1

Models and seed, then wire `Base.metadata.create_all` into the lifespan:

- `User` (single table; unique email; `hashed_password`; no `is_superuser`)
- `Role`, `Permission`
- `user_roles`, `role_permissions` association tables
- `Ticket` (owner FK, status enum, timestamps)
- `RefreshToken` (hashed token, expiry, revoked/replaced chain fields)
- Idempotent seed: permissions catalog, `customer`/`staff`/`admin` roles, explicit
  `role_permissions` matrix — admin holds every permission explicitly, no bypass
- Then `Base.metadata.create_all(engine)` in `app/main.py` lifespan
- Test: schema creation + seed idempotency against `rbac_learning_test`

After that: M1-2 auth (register/login, bcrypt cost 12, 15-min access JWT carrying only `sub`,
rotating opaque refresh cookie), M1-3 `require_permission` guard factory + matrix tests.

---

## 9. Gotcha cheat sheet

| Symptom | Cause | Fix |
|---|---|---|
| `localhost:8001` hangs, `127.0.0.1` works | Windows prefers `::1`; WSL IPv6 loopback not shared | Use `127.0.0.1` |
| MySQL stuck `activating`, log says port 3306 in use | Windows `MySQL80` owns 3306 under mirrored networking | WSL MySQL stays on 3307 |
| `Address already in use` on 8000 | Windows `postgres` | Use 8001 |
| `Access denied ... using password: YES` right after WSL boot | MySQL still starting | Wait for `systemctl is-active mysql` |
| `_pydantic_core.pyd` / `asyncmy` blocked | Smart App Control on Windows | Run inside WSL |
| `uv run` wants to rebuild `.venv` | Running uv from Windows | Run uv inside WSL |
| `set: pipefail: invalid option name` | Script saved with CRLF | Save shell scripts with LF |
