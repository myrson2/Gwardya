"""Admin routes (M1-5)."""

from fastapi import APIRouter, Depends

from app.api.deps import SessionDep, require_permission
from app.core.enums import PermissionCode
from app.models import User
from app.schemas.admin import PermissionResponse, RoleResponse, RoleUpdateRequest
from app.schemas.auth import UserResponse
from app.services import admin_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    session: SessionDep,
    _: User = Depends(require_permission(PermissionCode.USER_READ)),
) -> list[UserResponse]:
    users = await admin_service.list_users(session)
    return [UserResponse.from_user(user) for user in users]


@router.patch("/users/{user_id}/roles", response_model=UserResponse)
async def assign_user_roles(
    user_id: int,
    payload: RoleUpdateRequest,
    session: SessionDep,
    _: User = Depends(require_permission(PermissionCode.USER_ASSIGN_ROLE)),
) -> UserResponse:
    user = await admin_service.assign_roles(session, user_id, payload.roles)
    return UserResponse.from_user(user)


@router.get("/roles", response_model=list[RoleResponse])
async def list_roles(
    session: SessionDep,
    _: User = Depends(require_permission(PermissionCode.ROLE_READ)),
) -> list[RoleResponse]:
    roles = await admin_service.list_roles(session)
    return [RoleResponse.from_role(role) for role in roles]


@router.get("/permissions", response_model=list[PermissionResponse])
async def list_permissions(
    session: SessionDep,
    _: User = Depends(require_permission(PermissionCode.ROLE_READ)),
) -> list[PermissionResponse]:
    permissions = await admin_service.list_permissions(session)
    return [
        PermissionResponse(code=permission.code, description=permission.description)
        for permission in permissions
    ]
