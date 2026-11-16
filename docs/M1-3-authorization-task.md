# M1-3 task — implement the authorization core

You are implementing the heart of the project. Everything around it is finished: models, seed,
authentication, routes, services, and a written acceptance suite. Two files are yours, and the
whole RBAC story depends on them.

Read this document, then read the docstrings of the two stubs. Do not read the acceptance suite
first — write the implementation from the contract, then let the tests grade it.

---

## 1. Definition of done

- `app/api/deps.py` — `require_permission` and `require_any_permission` implemented.
- `app/services/ticket_scope.py` — `scope_tickets` implemented.
- `RUN_M1_3=1 uv run pytest tests/test_authorization.py -q` is green.
- `uv run pytest -q` stays green (the authorization suite is skipped without the env var).
- `uv run ruff check .` stays clean.
- No route, service, model, schema, or test file needs to change.

That is the entire M1-3 exit gate from `specs/roadmap.md`:

> customer calling a staff endpoint gets 403; no token gets 401; foreign ticket id gets 404.

---

## 2. What already exists (do not rebuild it)

| Piece | Location | Behaviour |
|---|---|---|
| `get_current_user` | `app/api/deps.py` | Parses the Bearer token, decodes it, loads the user **with roles and permissions** from MySQL, returns `User`. Raises 401 for missing/invalid/expired tokens. |
| `verify_origin` | `app/api/deps.py` | Exact Origin check for refresh/logout. Already used. |
| `User.permission_codes` | `app/models/user.py` | `frozenset[str]` of effective codes, resolved through roles. Requires the eager loads that `get_current_user` performs. |
| `User.role_names` | `app/models/user.py` | Display only. **Never use it for an access decision.** |
| Route wiring | `app/api/routes/*.py` | Routes already depend on `require_permission(...)` / `require_any_permission(...)`. You do not edit them. |
| Services | `app/services/ticket_service.py`, `admin_service.py` | Business rules and queries. `get_ticket`/`list_tickets` already call `scope_tickets`. |
| Error types | `app/services/errors.py` | `NotFoundError` → 404, `ConflictError` → 409, etc. |

The access token contains only `sub`, `iat`, `exp`, `typ`. It never contains roles or
permissions, so your guards must read the current grant set from the `User` that
`get_current_user` just loaded.

---

## 3. Contracts

### 3.1 `require_permission(code)` — all-of-one guard

```python
def require_permission(code: PermissionCode | str) -> Callable[..., Awaitable[User]]:
    ...
```

It is a **factory**: calling it with a code returns an async dependency. Routes use it as
`Depends(require_permission(PermissionCode.TICKET_CREATE))`.

Required behaviour:

1. Run only after `get_current_user` has succeeded. Identity failures are already 401 and must
   not be converted into something else.
2. If the user's effective permission set contains `code`, return that same `User`.
3. Otherwise raise `HTTPException(status_code=403, detail=...)`.
4. Decide from `user.permission_codes` only. Never inspect `role_names`, never decode the JWT,
   never import `app.core.catalog`, never accept a role or permission from the request body.
5. Returning the `User` matters: FastAPI injects it into the handler, and other dependencies can
   chain on it.

### 3.2 `require_any_permission(*codes)` — any-of guard

```python
def require_any_permission(*codes: PermissionCode | str) -> Callable[..., Awaitable[User]]:
    ...
```

Same rules, different membership test: allow when the user holds **at least one** of the
supplied codes. This exists because `GET /tickets` is legal for `ticket:read_own` *and* for
`ticket:read_all`, but each role holds only one of them. Deny with 403 when the sets are
disjoint.

Edge case worth handling deliberately: a user with no roles has an empty permission set. The
guard must deny (403), not crash, and not return 200 with an empty list.

### 3.3 `scope_tickets(stmt, user)` — ownership predicate

```python
def scope_tickets(stmt: Select[tuple[Ticket]], user: User) -> Select[tuple[Ticket]]:
    ...
```

It receives a `select(Ticket)` that may already contain `where` clauses and returns a statement
with the correct ownership restriction added. It must not execute anything and must not filter
in Python.

Required behaviour:

1. Holder of `ticket:read_all` → return the statement unchanged (sees every ticket).
2. Everyone else → return the statement with a predicate limiting rows to
   `tickets.customer_id == user.id`.
3. Decide from `user.permission_codes`, never from a role name and never from the JWT.
4. Preserve any clauses the caller already applied. Add to the statement; do not replace it.

Why this matters: `get_ticket` turns "row not visible to you" into `NotFoundError("Ticket not
found")`. That is how a foreign id becomes indistinguishable from a missing id (404 in both
cases, identical body). If you fetch first and compare in Python, you leak existence and
usually the timing as well.

---

## 4. The 401 / 403 / 404 decision table

| Situation | Status | Produced by |
|---|---|---|
| No `Authorization` header | 401 + `WWW-Authenticate: Bearer` | `get_current_user` (done) |
| Malformed, invalid, or expired token | 401 + `WWW-Authenticate: Bearer` | `get_current_user` (done) |
| Valid identity, lacks the required permission | 403 | **your guards** |
| Valid identity, permission held, ticket owned by someone else | 404, body `{"detail": "Ticket not found"}` | **your scope** + `get_ticket` |
| Valid identity, permission held, ticket does not exist | 404, same body | service |
| Valid identity, permission held, illegal status transition | 409 | `ticket_service` (done) |
| Valid identity, permission held, ticket owned | 2xx | service |

Rules of thumb:

- **401 means "I do not know who you are."** Only identity resolution may produce it.
- **403 means "I know who you are, and you may not perform this operation."** Only the route
  guard may produce it.
- **404 means "this resource is not in your scope."** It is deliberately not a permission
  error, and it must never reveal whether the row exists.
- A customer listing `/tickets` gets **200 with only their rows**, not 404 and not an empty
  list because of a Python filter.

---

## 5. Hints (not the solution)

1. `PermissionCode` is a `StrEnum`, and `user.permission_codes` is a `frozenset[str]`.
   Membership and set operations work naturally; `str(code)` is a safe explicit spelling.
2. `require_permission` is essentially: membership check → raise 403 → return user.
3. `require_any_permission` is the same shape with a set operation that answers "are these two
   sets disjoint?". Guard the deny path, then return the user.
4. `scope_tickets` is one branch and one `.where(...)`. The comparison is between the ticket
   column and the authenticated user's primary key.
5. Use `fastapi.status.HTTP_403_FORBIDDEN` and a stable detail such as `"Forbidden"` or
   `"Missing permission: ticket:read_all"`. The acceptance suite asserts status codes, not
   exact detail text; the frontend will display whatever you choose.
6. Do not catch or translate `HTTPException`. Let it propagate.
7. Do not add a superuser bypass. Admin holds every permission explicitly in the seed; that is
   the whole point of the matrix.

### Common mistakes

| Mistake | Why it fails |
|---|---|
| Checking `user.role_names` | Roles are bundles; a role rename or a new role breaks the check. |
| Decoding the token again | Grants are not in the token. It would always deny. |
| Importing `ROLE_PERMISSIONS` from the catalog | Code becomes the authority; the database must be. Role edits would not take effect. |
| Fetching all tickets then filtering in Python | Leaks existence/timing; violates the SQL-scoping requirement. |
| Raising 404 from a route guard | A missing permission is about the operation, not a resource. It must be 403. |
| Raising 403 for a foreign ticket | Leaks that the ticket exists. Must be 404. |
| Returning `None` from a guard | Handlers and downstream dependencies expect the `User`. |
| Handling missing tokens inside the guard | `get_current_user` already did; duplicating it risks returning 403 instead of 401. |
| Editing tests or routes to make things pass | The point is the implementation; the suite is the grader. |

---

## 6. Run the acceptance suite

The suite is skipped by default:

```bash
cd /mnt/c/Users/merss/Documents/RBAC-PROJECT/backend
uv run pytest -q                       # 32 passed, 18 skipped
```

Turn it on after implementing:

```bash
RUN_M1_3=1 uv run pytest tests/test_authorization.py -q
```

What each test proves:

| Test | Contract |
|---|---|
| `test_permission_matrix` | Every role × protected route returns the seeded expectation (customer/staff/admin) |
| `test_missing_token_is_401` | 401 + `WWW-Authenticate: Bearer` on every protected route |
| `test_invalid_token_is_401` | Garbage Bearer token is still 401 |
| `test_valid_identity_without_grant_is_403_not_401` | Known customer on an admin route is 403, not 401 |
| `test_foreign_ticket_is_404_and_indistinguishable` | Bob reading Alice's ticket and a missing id both return 404 with identical bodies; staff/admin/alice get 200 |
| `test_list_scoping_follows_ownership` | Customer lists exactly their rows; staff/admin list all rows |
| `test_create_ticket_takes_ownership_from_identity` | A body-supplied `customer_id`/`status` cannot change ownership or initial status |
| `test_role_change_applies_to_the_next_request` | Promote customer→staff: same token immediately gains `ticket:update_status`; demote: immediately loses it |
| `test_any_of_guard_denies_identity_without_grants` | A user with zero roles gets 403 on `GET /tickets` |
| `test_me_reports_permissions_resolved_from_mysql` | `/auth/me` reflects the seeded customer codes |
| `test_closed_ticket_is_final` | Business rule still returns 409 (regression guard) |

If you prefer a failing-first loop, run one test at a time while implementing:

```bash
RUN_M1_3=1 uv run pytest tests/test_authorization.py::test_permission_matrix -q
```

---

## 7. Manual verification

Start the API in WSL (step 2 in `BOILERPLATE.md`), then:

```bash
BASE=http://127.0.0.1:8001

TOKEN=$(curl -s -X POST "$BASE/auth/login" \
  -H 'Content-Type: application/json' \
  -d '{"email":"alice@example.com","password":"DevPassw0rd!"}' \
  | python -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')

# Identity and DB-resolved grants
curl -s "$BASE/auth/me" -H "Authorization: Bearer $TOKEN"

# Customer -> staff-only endpoint: expect 403
curl -s -o /dev/null -w '%{http_code}\n' "$BASE/admin/users" \
  -H "Authorization: Bearer $TOKEN"

# Customer listing: expect 200 with only Alice's rows
curl -s "$BASE/tickets" -H "Authorization: Bearer $TOKEN"

# No token: expect 401
curl -s -o /dev/null -w '%{http_code}\n' "$BASE/tickets"
```

For the IDOR check, log in as `staff@example.com`, list `/tickets`, pick a ticket whose
`customer_id` is not Alice's, then request it with Alice's token. Expect **404**, exactly as if
the id did not exist.

> Login sets an httpOnly refresh cookie too; that is unrelated to these checks and is handled by
> the completed auth layer.

---

## 8. Acceptance checklist

- [ ] `require_permission` returns the same `User` on success and raises 403 on a missing code.
- [ ] `require_any_permission` allows when at least one code matches and raises 403 otherwise,
      including the empty-grant case.
- [ ] Both guards read `user.permission_codes`; no role names, no token decoding, no catalog.
- [ ] `scope_tickets` returns the statement unchanged for `ticket:read_all`.
- [ ] `scope_tickets` adds a SQL predicate for everyone else, preserving existing clauses.
- [ ] `RUN_M1_3=1 uv run pytest tests/test_authorization.py -q` → all 18 pass.
- [ ] `uv run pytest -q` → 50 passed (or 32 passed + 18 skipped when the env var is absent).
- [ ] `uv run ruff check .` → clean.
- [ ] `/docs` loads; manual checks above return 403 / 404 / 401 as specified.

When this is green, M1-3 is complete and the backend RBAC vertical slice is functional end to
end.
