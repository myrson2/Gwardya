"""M1-3 acceptance suite — the authorization contract you must implement.

The module is skipped by default so the boilerplate suite stays green. Once
``require_permission``, ``require_any_permission`` and ``scope_tickets`` are
implemented, run::

    RUN_M1_3=1 uv run pytest tests/test_authorization.py -q

Every test drives the public HTTP surface and never imports the guards, so a green
run also proves the stubs are wired into the routes. See
``docs/M1-3-authorization-task.md`` for the contracts and hints.
"""

import os

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_M1_3") != "1",
    reason="M1-3 exercise not implemented; set RUN_M1_3=1 when ready",
)

ALICE = "alice@example.com"
BOB = "bob@example.com"
STAFF = "staff@example.com"
ADMIN = "admin@example.com"


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _user_id(session: AsyncSession, email: str) -> int:
    value = await session.scalar(
        text("SELECT id FROM users WHERE email = :email"), {"email": email}
    )
    assert value is not None
    return int(value)


async def _ticket_id(session: AsyncSession, title: str) -> int:
    value = await session.scalar(
        text("SELECT id FROM tickets WHERE title = :title"), {"title": title}
    )
    assert value is not None
    return int(value)


async def _owned_ticket_ids(session: AsyncSession, user_id: int) -> set[int]:
    rows = await session.scalars(
        text("SELECT id FROM tickets WHERE customer_id = :id"), {"id": user_id}
    )
    return {int(row) for row in rows}


async def test_permission_matrix(client: AsyncClient, login, db_session) -> None:
    """The seeded matrix from ``specs/roadmap.md`` M1-3/M1-4, end to end."""
    alice_ticket = await _ticket_id(db_session, "Printer will not connect")
    bob_id = await _user_id(db_session, BOB)

    tokens = {
        "customer": await login(ALICE),
        "staff": await login(STAFF),
        "admin": await login(ADMIN),
    }

    cases: list[tuple[str, str, dict | None, dict[str, int]]] = [
        (
            "GET",
            "/tickets",
            None,
            {"customer": 200, "staff": 200, "admin": 200},
        ),
        (
            "GET",
            f"/tickets/{alice_ticket}",
            None,
            {"customer": 200, "staff": 200, "admin": 200},
        ),
        (
            "POST",
            "/tickets",
            {"title": "Matrix probe", "description": "created by the matrix test"},
            {"customer": 201, "staff": 403, "admin": 201},
        ),
        (
            "PATCH",
            f"/tickets/{alice_ticket}/status",
            {"status": "in_progress"},
            {"customer": 403, "staff": 200, "admin": 200},
        ),
        (
            "GET",
            "/admin/users",
            None,
            {"customer": 403, "staff": 403, "admin": 200},
        ),
        (
            "GET",
            "/admin/roles",
            None,
            {"customer": 403, "staff": 403, "admin": 200},
        ),
        (
            "GET",
            "/admin/permissions",
            None,
            {"customer": 403, "staff": 403, "admin": 200},
        ),
        (
            "PATCH",
            f"/admin/users/{bob_id}/roles",
            {"roles": ["customer"]},
            {"customer": 403, "staff": 403, "admin": 200},
        ),
    ]

    for method, path, body, expected in cases:
        for role, status_code in expected.items():
            response = await client.request(
                method, path, json=body, headers=_bearer(tokens[role])
            )
            assert response.status_code == status_code, (
                f"{role} {method} {path} -> {response.status_code}: {response.text}"
            )


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("GET", "/tickets", None),
        ("POST", "/tickets", {"title": "x", "description": "x"}),
        ("GET", "/tickets/1", None),
        ("PATCH", "/tickets/1/status", {"status": "in_progress"}),
        ("GET", "/admin/users", None),
        ("PATCH", "/admin/users/1/roles", {"roles": []}),
        ("GET", "/admin/roles", None),
        ("GET", "/admin/permissions", None),
    ],
)
async def test_missing_token_is_401(
    client: AsyncClient, method: str, path: str, body: dict | None
) -> None:
    response = await client.request(method, path, json=body)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


async def test_invalid_token_is_401(client: AsyncClient) -> None:
    response = await client.get(
        "/tickets", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401


async def test_valid_identity_without_grant_is_403_not_401(
    client: AsyncClient, login
) -> None:
    customer = _bearer(await login(ALICE))
    response = await client.get("/admin/users", headers=customer)
    assert response.status_code == 403
    assert "www-authenticate" not in response.headers


async def test_foreign_ticket_is_404_and_indistinguishable(
    client: AsyncClient, login, db_session
) -> None:
    alice_ticket = await _ticket_id(db_session, "Printer will not connect")
    bob = _bearer(await login(BOB))

    foreign = await client.get(f"/tickets/{alice_ticket}", headers=bob)
    missing = await client.get("/tickets/999999", headers=bob)

    assert foreign.status_code == 404
    assert missing.status_code == 404
    # A foreign id must not be distinguishable from an absent one.
    assert foreign.json() == missing.json()

    alice = _bearer(await login(ALICE))
    staff = _bearer(await login(STAFF))
    admin = _bearer(await login(ADMIN))
    assert (
        await client.get(f"/tickets/{alice_ticket}", headers=alice)
    ).status_code == 200
    assert (
        await client.get(f"/tickets/{alice_ticket}", headers=staff)
    ).status_code == 200
    assert (
        await client.get(f"/tickets/{alice_ticket}", headers=admin)
    ).status_code == 200


async def test_list_scoping_follows_ownership(
    client: AsyncClient, login, db_session
) -> None:
    alice_id = await _user_id(db_session, ALICE)
    bob_id = await _user_id(db_session, BOB)
    alice_ids = await _owned_ticket_ids(db_session, alice_id)
    bob_ids = await _owned_ticket_ids(db_session, bob_id)

    alice = _bearer(await login(ALICE))
    alice_body = (await client.get("/tickets", headers=alice)).json()
    assert {ticket["id"] for ticket in alice_body} == alice_ids
    assert all(ticket["customer_id"] == alice_id for ticket in alice_body)

    bob = _bearer(await login(BOB))
    bob_body = (await client.get("/tickets", headers=bob)).json()
    assert {ticket["id"] for ticket in bob_body} == bob_ids
    assert all(ticket["customer_id"] == bob_id for ticket in bob_body)

    for email in (STAFF, ADMIN):
        headers = _bearer(await login(email))
        body = (await client.get("/tickets", headers=headers)).json()
        assert {ticket["id"] for ticket in body} == alice_ids | bob_ids


async def test_create_ticket_takes_ownership_from_identity(
    client: AsyncClient, login, db_session
) -> None:
    alice_id = await _user_id(db_session, ALICE)
    bob_id = await _user_id(db_session, BOB)

    response = await client.post(
        "/tickets",
        headers=_bearer(await login(ALICE)),
        json={
            "title": "Owner probe",
            "description": "the body must not choose the owner",
            "customer_id": bob_id,
            "status": "closed",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["customer_id"] == alice_id
    assert body["status"] == "open"


async def test_role_change_applies_to_the_next_request(
    client: AsyncClient, login, db_session
) -> None:
    """The access token carries no grants, so no re-login is needed after a role change."""
    alice_id = await _user_id(db_session, ALICE)
    alice_ticket = await _ticket_id(db_session, "Printer will not connect")
    alice = _bearer(await login(ALICE))
    admin = _bearer(await login(ADMIN))

    async def update_status():
        return await client.patch(
            f"/tickets/{alice_ticket}/status",
            json={"status": "in_progress"},
            headers=alice,
        )

    assert (await update_status()).status_code == 403

    promote = await client.patch(
        f"/admin/users/{alice_id}/roles",
        json={"roles": ["staff"]},
        headers=admin,
    )
    assert promote.status_code == 200
    assert promote.json()["roles"] == ["staff"]
    assert (await update_status()).status_code == 200

    demote = await client.patch(
        f"/admin/users/{alice_id}/roles",
        json={"roles": ["customer"]},
        headers=admin,
    )
    assert demote.status_code == 200
    assert (await update_status()).status_code == 403


async def test_any_of_guard_denies_identity_without_grants(
    client: AsyncClient, login, db_session
) -> None:
    password = "NoGrantPassw0rd!"
    registered = await client.post(
        "/auth/register",
        json={"email": "nobody@example.com", "password": password},
    )
    assert registered.status_code == 201
    nobody_id = await _user_id(db_session, "nobody@example.com")

    stripped = await client.patch(
        f"/admin/users/{nobody_id}/roles",
        json={"roles": []},
        headers=_bearer(await login(ADMIN)),
    )
    assert stripped.status_code == 200

    nobody = _bearer(await login("nobody@example.com", password))
    response = await client.get("/tickets", headers=nobody)
    assert response.status_code == 403


async def test_me_reports_permissions_resolved_from_mysql(
    client: AsyncClient, login
) -> None:
    response = await client.get("/auth/me", headers=_bearer(await login(ALICE)))
    assert response.status_code == 200
    body = response.json()
    assert body["roles"] == ["customer"]
    assert set(body["permissions"]) == {"ticket:create", "ticket:read_own"}


async def test_closed_ticket_is_final(client: AsyncClient, login, db_session) -> None:
    closed_ticket = await _ticket_id(db_session, "Invoice copy request")
    staff = _bearer(await login(STAFF))
    response = await client.patch(
        f"/tickets/{closed_ticket}/status", json={"status": "open"}, headers=staff
    )
    assert response.status_code == 409
