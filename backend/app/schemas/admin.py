from pydantic import BaseModel, Field

from app.core.enums import RoleName
from app.models import Role


class RoleUpdateRequest(BaseModel):
    roles: list[RoleName] = Field(default_factory=list)


class RoleResponse(BaseModel):
    name: str
    description: str
    permissions: list[str]

    @classmethod
    def from_role(cls, role: Role) -> RoleResponse:
        return cls(
            name=role.name,
            description=role.description,
            permissions=sorted(permission.code for permission in role.permissions),
        )


class PermissionResponse(BaseModel):
    code: str
    description: str
