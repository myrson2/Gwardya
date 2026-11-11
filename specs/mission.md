# Mission — RBAC Learning Project

## Executive Summary

Build a complete, runnable support-ticket application whose authorization layer demonstrates
real role-based access control: one identity, data-driven roles and permissions, ownership-aware
reads, rotating refresh tokens, and an executable permission matrix.

The application is the vehicle. The durable outcome is the developer's ability to design and
implement RBAC unaided.

## The Problem & Industry Friction

Most RBAC tutorials stop at `if user.role == "admin"`. They skip the parts that break real
systems:

- ownership rules (a customer must not read another customer's ticket);
- stale authorization (roles embedded in long-lived JWTs);
- refresh-token revocation and reuse;
- mass assignment (a client registering itself as admin);
- the difference between 401, 403, and 404.

Full-stack examples are usually fragmented: a backend snippet here, a frontend guard there, and
no tests proving the permission matrix.

## Target Persona

**Primary (learning) persona:** a developer who understands RBAC conceptually but has not
implemented it end-to-end. Has built FastAPI endpoints, used async/await and JWT login; can read
React but is rusty writing it. Studies in short daily sessions.

**Application personas:**

- **Customer** — registers, creates tickets, reads only their own, cannot change status.
- **Staff** — reads all tickets, moves status through open → in_progress → closed.
- **Admin** — everything staff can do, plus lists users and assigns roles.

## Value Proposition

- One repository with the full vertical slice: MySQL schema, async FastAPI, JWT + refresh
  rotation, React UI, and tests.
- Every security decision is explicit and justified; rejected alternatives are documented.
- The permission matrix is code, not prose.
- Built in small, runnable daily increments with Socratic checkpoints.

## Success Metrics (KPIs)

**Learning outcomes**

- Implement `require_permission` and the ownership rule from a blank file, unaided.
- Explain when the API returns 401 vs 403 vs 404, with an example of each.
- Add a new permission and wire it to a role in under 15 minutes without editing route bodies.
- Pass a 10-question oral review at the end of M1 and M3.

**Product outcomes**

- 100% of permission-matrix tests pass.
- Customer B receives 404 for customer A's ticket id.
- A rotated refresh token cannot be reused; logout invalidates the session.
- A registration payload containing `"role": "admin"` still creates a customer.
- Frontend hides forbidden actions **and** the API independently rejects them.

**Process outcomes**

- Every session ends runnable.
- Zero secrets in git.
- Specs and code agree at the end of each phase.

## Non-Goals

- Production deployment, scaling, or high availability.
- A polished commercial UI.
- Email, OAuth, MFA, password reset.
- Ticket replies/attachments (M3 graduation exercise).
- Multi-tenancy.
