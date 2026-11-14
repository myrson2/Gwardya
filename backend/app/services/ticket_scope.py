"""Ownership scoping — the second half of M1-3 (the exercise).

Roadmap M1-3: "Ownership helper for ``read_own``; 401/403/404 semantics."

The whole point is that scoping happens **in SQL**, not by fetching a row and comparing
``ticket.customer_id`` in Python. A foreign id must behave exactly like a missing id:
404, so an attacker cannot probe for existence (Constitution §2.3).
"""

from sqlalchemy import Select

from app.models import Ticket, User

STUDENT_TASK = (
    "M1-3 student task: implement scope_tickets() in app/services/ticket_scope.py. "
    "See docs/M1-3-authorization-task.md."
)


def scope_tickets(stmt: Select[tuple[Ticket]], user: User) -> Select[tuple[Ticket]]:
    """Restrict a ticket query to what ``user`` is allowed to see.

    Contract
    --------
    * The caller passes a ``select(Ticket)`` that may already have ``where`` clauses.
    * Return the statement with the correct ownership predicate applied.
    * A holder of ``ticket:read_all`` sees every ticket; everyone else sees only rows
      whose ``customer_id`` equals ``user.id``.
    * Decide from the **permission set** (``user.permission_codes``), never from a role
      name and never from the JWT.
    * Do not execute the statement here. Do not post-filter in Python.

    A correct implementation is roughly one ``if`` and one ``.where(...)``.
    """
    raise NotImplementedError(STUDENT_TASK)
