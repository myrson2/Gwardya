# Roadmap — RBAC Learning Project

Pace assumption: under 4 focused hours/week, 5–6 sessions/week of ~40 minutes.
Total ≈ 40–42 sessions (~7–9 weeks). We reassess after M1-2a and cut scope, never the RBAC core.

## Phase Overview

| Phase | Theme | Exit criteria |
|---|---|---|
| **M1** | Backend RBAC core | All backend endpoints work; permission-matrix and IDOR tests pass; Swagger demo of all three roles |
| **M2** | Frontend + Access Inspector | Login, token refresh, three dashboards, guards; forbidden calls visibly return 403 while the UI hides the action |
| **M3** | Hardening + graduation | Reuse detection, full matrix, docs; Pattern Lab refactor; you add ticket replies yourself using the same pattern |

---

## M1 — Backend RBAC Core (≈21 sessions)

### M1-0 Environment & database (2 sessions)
- `uv` venv, dependencies, `backend/.env` from `.env.example`.
- Run `backend/db/setup.sql` as root: schema `rbac_learning`, user `rbac_app`, least-privilege grants.
- Verify the async connection with `/health/db`.
- **Exit:** app boots; `/health/db` returns `ok`.

### M1-1 Models & seed (3 sessions, I write the reference slice)
- Models: `User`, `Role`, `Permission`, `Ticket`, `RefreshToken` + association tables.
- `create_all` and idempotent `seed.py`: 2 customers, 1 staff, 1 admin, permission catalog,
  sample tickets.
- **Exit:** tables visible in MySQL; seed re-runs without duplicates.

### M1-2a Authentication: register, login, access token (4 sessions)
- bcrypt hashing in threadpool; JWT issue/decode; `get_current_user`.
- `POST /auth/register` (forces customer), `POST /auth/login`.
- **Exit:** login returns a 15-min access token; `/auth/me` works; bad password → 401.

### M1-2b Refresh rotation, logout, revocation (5 sessions)
- `refresh_tokens` persistence, hashed values, cookie handling, rotation, `replaced_by_id`,
  logout, Origin check.
- **Exit:** refresh returns a new pair and revokes the old token; reuse revokes the chain;
  logout clears the cookie.

### M1-3 Authorization core (4 sessions — the heart)
- `require_permission(code)` dependency factory; DB-resolved permissions with `selectinload`.
- Ownership helper for `read_own`; 401/403/404 semantics.
- **Exit:** customer calling a staff endpoint gets 403; no token gets 401; foreign ticket id gets 404.

### M1-4 Ticket API (5 sessions)
- `POST /tickets`, `GET /tickets` (own vs all), `GET /tickets/{id}` (own vs all),
  `PATCH /tickets/{id}/status` (staff).
- Permission-matrix and IDOR tests.
- **Exit:** matrix tests pass for customer/staff/admin; `closed` is final.

### M1-5 Admin API (3 sessions)
- `GET /admin/users`, `PATCH /admin/users/{id}/roles`, `GET /admin/roles`,
  `GET /admin/permissions`.
- **Exit:** only `user:read` / `user:assign_role` holders succeed; a role change is visible on
  the next request (no token reissue).

**M1 exit gate:** Swagger walkthrough for all three roles + green backend test suite.

---

## M2 — Frontend + Access Inspector (≈8–10 sessions)

### M2-1 Shell & auth context (3 sessions, I scaffold)
- Vite + React Router; in-memory access token; login page; logout.
- `fetch` wrapper with one retry on 401 via `/auth/refresh`.

### M2-2 Dashboards & guards (4 sessions, you wire)
- Customer: list own tickets, create ticket.
- Staff: list all, change status.
- Admin: users + role assignment.
- `RequireAuth` and `RequirePermission` guards; nav renders from permissions.

### M2-3 Access Inspector (1–2 sessions)
- Decode and display the token payload; show roles/permissions.
- Buttons that call forbidden endpoints to demonstrate 403 vs hidden UI.

**M2 exit gate:** each demo account sees the correct UI; manual forbidden calls still return 403.

---

## M3 — Hardening & Graduation (≈6–8 sessions)

- Full permission matrix; revoked-refresh and reuse-detection tests.
- Registration mass-assignment regression test.
- README: run instructions, permission catalog, architecture diagram, trade-offs.
- **Graduation exercise (you implement):** add `ticket_messages` (replies) with
  `reply_own` / `reply_all`, using the same permission + ownership pattern, with tests.

### M3 Pattern Lab (≈2 sessions)
- Refactor ticket visibility or status transitions into a **Strategy** (`TicketAccessPolicy` /
  `StatusTransitionPolicy`): pure, testable policies with explicit unknown-role denial.
- Compare before/after: lines of code, testability, and why the permission guard still owns the
  "may you attempt this?" decision.
- Document **Factory Method** as deferred — only justified if role-specific profile data or
  multiple hasher algorithms appear.

**M3 exit gate:** suite green; the permission matrix stays green after the Pattern Lab; you can
add a new resource end-to-end without guidance and explain permission vs business-policy
separation.

---

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Async lazy-loading errors (`MissingGreenlet`) | Explicit `selectinload` in every query; seed examples show the pattern |
| Refresh rotation feels abstract | Draw the token state machine before coding; test each transition |
| React rustiness | I scaffold the shell; you copy an existing page pattern for the next one |
| Under-4h weeks | Sessions are 40 min; each ends runnable; scope cuts are explicit |
| MySQL auth/paths on Windows | Full `mysql.exe` path + one command; app uses a dedicated non-root user |
| Pattern Lab becomes over-engineering | Constitution axiom 8 + selection checklist in `specs/design-patterns.md` |
