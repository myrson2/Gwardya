# Design Patterns — Learning Appendix

**Status:** Living document · **Applies to:** M1–M3
**Rule:** a pattern is added only when a present problem demands it (Constitution axiom 8).

The project domain is **support tickets** (customer/staff/admin). Library examples
(student/staff/librarian, books) are used as a neutral teaching domain because they are
familiar and independent of our schema.

## 1. Pattern Map

| Pattern | Status | Where | Solves |
|---|---|---|---|
| Guard dependency factory | **In M1** | `require_permission(code)` in `app/api/deps.py` | Repeated authorization checks across routes |
| Strategy | **M3 Pattern Lab** | `TicketAccessPolicy` / `StatusTransitionPolicy` | Role-specific business rules after permission is granted |
| Factory Method / Simple Factory | **Deferred** | Profile creation or multi-algorithm hashing, *if* they appear | Centralised creation of role-specific objects |
| (GoF) Decorator | **Not used** | — | FastAPI dependencies cover the wrapping need; naming it "Decorator" would be imprecise |

## 2. Guard Dependency Factory (M1)

**Problem:** every protected route must reject anonymous users (401) and users lacking a
permission (403) without duplicating code.

**Why permissions, not roles:** role-name checks (`if role == "librarian"`) couple code to
data. Adding a role means editing every route. A permission code is data; roles are bundles of
permission codes.

**Sketch (neutral domain):**

```python
def require_permission(code: str):
    async def guard(user: User = Depends(get_current_user)) -> User:
        if code not in user.permission_codes:      # resolved from DB, not JWT
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return guard
```

**Rules**
- `get_current_user` owns 401 (identity); the guard owns 403 (authorization).
- Never read roles/permissions from the access token; load them from MySQL per request.
- With many-to-many roles, there is no `user.role` attribute; use the permission set.
- The guard returns the user so route handlers can use it.

**Anti-pattern:** `require_roles(["librarian", "staff"])` — brittle and duplicates the
permission catalog in code.

## 3. Strategy (M3 Pattern Lab)

**Problem:** after authorization passes, some rules still vary by role. Example: staff may move
a ticket `open → in_progress → closed`; admin may also reopen; customers may not change status
at all.

**Key distinction**
- **Permission:** *may you attempt this action?* (`ticket:update_status`)
- **Strategy:** *given that you may, what are the rules?* (which transitions are legal)

**Sketch (neutral domain):**

```python
class StatusTransitionPolicy(Protocol):
    def allowed(self, current: str, target: str) -> bool: ...

class StaffTransitionPolicy:
    def allowed(self, current, target):
        return (current, target) in {
            ("open", "in_progress"),
            ("in_progress", "closed"),
        }

class AdminTransitionPolicy:
    def allowed(self, current, target):
        return target in {"open", "in_progress", "closed"}
```

**Rules**
- Policies are **pure**: pass the current state in, return a decision. No DB queries inside.
- Select the policy explicitly; an unknown role must **deny**, never silently fall back to a
  permissive policy.
- Strategy does not replace the permission guard; both run.
- Introduce it only after the simple version exists, so the refactor has a measurable payoff.

**Anti-pattern:** a `get_policy(role)` that defaults unknown roles to a student/user policy.

## 4. Factory Method / Simple Factory (deferred)

**Problem it would solve:** creating the right role-specific object when role-specific data
exists — e.g., `CustomerProfile` (shipping address) vs `StaffProfile` (department).

**Current decision:** our constitution uses one `users` table and no profile tables, so a
profile factory has nothing to create. Adding it now would be speculative generality.

**When to revisit**
- we add 1:1 profile tables, or
- we support more than one password hashing algorithm (a `PasswordHasherFactory`).

**Naming**
- **Simple Factory:** one function with `if/elif` returning different types.
- **Factory Method:** subclasses override a creation method; the caller depends on an interface.

Both are valid; use the precise name.

## 5. Selection Checklist

Before adding a pattern, answer:

1. What duplication or variation exists **today**?
2. What breaks if we keep the simple version?
3. Is the pattern replacing authorization (wrong) or business rules (right)?
4. Can the new abstraction be tested without a database?
5. What is the rejected alternative, and why is it worse **now**?

If questions 1–2 have no concrete answer, do not add the pattern.

## 6. Exercises

1. **Guard:** implement `require_permission("ticket:read_all")` and prove 401 vs 403 with two
   tests. *Done when:* no route body contains a role name.
2. **Strategy:** refactor status transitions into a policy and keep the permission matrix green.
   *Done when:* a table-driven test covers every `(current, target)` pair.
3. **Factory (optional):** sketch a `ProfileFactory` for a library domain (student/staff/
   librarian) and list the three conditions that would justify it in this project.

## 7. Socratic Questions

1. Why does adding a role require editing zero route files in a permission-based design?
2. When does a Strategy become an over-engineered permission check?
3. What would you need to see in the codebase before introducing a Factory?
