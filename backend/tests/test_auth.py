"""V-19 .. — authentication, token shape, rotation, reuse, and logout (M1-2)."""

from httpx import AsyncClient

from app.core.config import settings
from app.core.security import REFRESH_COOKIE_NAME, decode_access_token

ORIGIN = {"origin": settings.frontend_origin}


async def _login(
    client: AsyncClient, email: str = "alice@example.com"
) -> tuple[str, str]:
    response = await client.post(
        "/auth/login",
        json={"email": email, "password": settings.seed_dev_password},
    )
    assert response.status_code == 200, response.text
    token = response.cookies.get(REFRESH_COOKIE_NAME)
    assert token is not None
    return response.json()["access_token"], token


async def _refresh_with(client: AsyncClient, token: str):
    client.cookies.clear()
    return await client.post(
        "/auth/refresh",
        headers=ORIGIN,
        cookies={REFRESH_COOKIE_NAME: token},
    )


async def test_register_forces_customer_and_ignores_mass_assignment(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/auth/register",
        json={
            "email": "Mallory@Example.com",
            "password": "Passw0rd!",
            "full_name": "Mallory",
            "role": "admin",
            "roles": ["admin"],
            "permissions": ["user:read"],
            "is_superuser": True,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["email"] == "mallory@example.com"
    assert body["roles"] == ["customer"]
    assert body["permissions"] == ["ticket:create", "ticket:read_own"]


async def test_register_rejects_duplicate_email(client: AsyncClient) -> None:
    response = await client.post(
        "/auth/register",
        json={"email": "alice@example.com", "password": "Passw0rd!"},
    )
    assert response.status_code == 409


async def test_register_rejects_password_over_72_bytes(client: AsyncClient) -> None:
    response = await client.post(
        "/auth/register",
        json={"email": "long@example.com", "password": "a" * 73},
    )
    assert response.status_code == 422


async def test_register_counts_utf8_bytes_not_characters(
    client: AsyncClient,
) -> None:
    # 40 characters but 80 UTF-8 bytes: must be rejected, not silently truncated.
    response = await client.post(
        "/auth/register",
        json={"email": "multibyte@example.com", "password": "é" * 40},
    )
    assert response.status_code == 422

    accepted = await client.post(
        "/auth/register",
        json={"email": "exact@example.com", "password": "a" * 72},
    )
    assert accepted.status_code == 201


async def test_login_sets_secure_cookie_and_hardened_flags(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/auth/login",
        json={"email": "alice@example.com", "password": settings.seed_dev_password},
    )
    assert response.status_code == 200
    set_cookie = response.headers["set-cookie"]
    assert REFRESH_COOKIE_NAME in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Path=/auth" in set_cookie
    assert "SameSite=lax" in set_cookie


async def test_access_token_carries_identity_only(client: AsyncClient) -> None:
    access, _ = await _login(client)
    payload = decode_access_token(access)
    assert payload["typ"] == "access"
    assert str(payload["sub"]).isdigit()
    assert set(payload) == {"sub", "iat", "exp", "typ"}


async def test_login_failures_are_generic(client: AsyncClient) -> None:
    wrong_password = await client.post(
        "/auth/login",
        json={"email": "alice@example.com", "password": "WrongPassw0rd!"},
    )
    unknown_user = await client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": "WrongPassw0rd!"},
    )
    assert wrong_password.status_code == 401
    assert unknown_user.status_code == 401
    assert wrong_password.json() == unknown_user.json()
    assert wrong_password.json()["detail"] == "Invalid email or password"


async def test_me_requires_a_valid_access_token(client: AsyncClient) -> None:
    assert (await client.get("/auth/me")).status_code == 401
    assert (
        await client.get("/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    ).status_code == 401

    access, _ = await _login(client)
    response = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {access}"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["roles"] == ["customer"]
    assert body["permissions"] == ["ticket:create", "ticket:read_own"]


async def test_refresh_rotates_and_reuse_revokes_the_chain(
    client: AsyncClient,
) -> None:
    _, first = await _login(client)

    rotated = await _refresh_with(client, first)
    assert rotated.status_code == 200, rotated.text
    second = rotated.cookies.get(REFRESH_COOKIE_NAME)
    assert second is not None
    assert second != first

    reused = await _refresh_with(client, first)
    assert reused.status_code == 401
    assert REFRESH_COOKIE_NAME in reused.headers.get("set-cookie", "")

    # The chain is dead: the replacement no longer works either.
    assert (await _refresh_with(client, second)).status_code == 401


async def test_logout_revokes_refresh_token(client: AsyncClient) -> None:
    _, token = await _login(client)
    logout = await client.post(
        "/auth/logout", headers=ORIGIN, cookies={REFRESH_COOKIE_NAME: token}
    )
    assert logout.status_code == 204
    assert (await _refresh_with(client, token)).status_code == 401


async def test_refresh_and_logout_enforce_origin(client: AsyncClient) -> None:
    _, token = await _login(client)
    client.cookies.clear()

    assert (
        await client.post(
            "/auth/refresh", cookies={REFRESH_COOKIE_NAME: token}
        )
    ).status_code == 403
    assert (
        await client.post(
            "/auth/logout", cookies={REFRESH_COOKIE_NAME: token}
        )
    ).status_code == 403

    # The rejected refresh did not consume the token.
    assert (await _refresh_with(client, token)).status_code == 200


async def test_refresh_requires_post_and_cookie(client: AsyncClient) -> None:
    assert (await client.get("/auth/refresh")).status_code == 405
    assert (
        await client.post("/auth/refresh", headers=ORIGIN)
    ).status_code == 401
