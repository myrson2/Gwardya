# `GET /admin/permissions` — Request Flow

Paste any block below into <https://mermaid.live> (or a Markdown preview with Mermaid support).

## 1. Sequence diagram

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
    participant API as FastAPI Router
    participant CU as get_current_user
    participant DB as MySQL
    participant G as require_permission
    participant H as list_permissions
    participant S as admin_service

    C->>API: GET /admin/permissions with Bearer access token

    API->>CU: Resolve auth dependency
    alt Missing or invalid token
        CU-->>API: 401 Unauthorized
        API-->>C: 401 {"detail": "Not authenticated"}
    else Valid token
        CU->>DB: SELECT user + roles + permissions (eager load)
        DB-->>CU: User with permission_codes
        CU-->>API: Authenticated User

        API->>G: Resolve guard with User
        alt "role:read" not in permission_codes
            G-->>API: 403 Forbidden
            API-->>C: 403 {"detail": "Permission denied"}
        else Permission granted
            G-->>API: User

            API->>H: Call handler(session)
            H->>S: list_permissions(session)
            S->>DB: SELECT permissions ORDER BY code
            DB-->>S: Permission rows
            S-->>H: Sequence[Permission]
            H-->>API: list[PermissionResponse]
            API-->>C: 200 JSON array of permissions
        end
    end
```

## 2. Authorization decision

```mermaid
flowchart TD
    A["GET /admin/permissions"] --> B{"Bearer token present?"}
    B -- "No" --> E401["401 Not authenticated"]
    B -- "Yes" --> C{"Token decodes and user exists?"}
    C -- "No" --> E401
    C -- "Yes" --> D{"role:read in user.permission_codes?"}
    D -- "No" --> E403["403 Permission denied"]
    D -- "Yes" --> F["admin_service.list_permissions(session)"]
    F --> G["SELECT code, description FROM permissions ORDER BY code"]
    G --> H["Build PermissionResponse objects"]
    H --> I["200 list of permissions"]
```

## 3. Where `role:read` comes from

```mermaid
erDiagram
    users ||--o{ user_roles : holds
    roles ||--o{ user_roles : assigned_to
    roles ||--o{ role_permissions : grants
    permissions ||--o{ role_permissions : granted_by

    users {
        int id PK
        varchar email UK
        varchar hashed_password
        varchar full_name
    }
    roles {
        int id PK
        varchar name UK
    }
    permissions {
        int id PK
        varchar code UK
        text description
    }
    user_roles {
        int user_id PK
        int role_id PK
    }
    role_permissions {
        int role_id PK
        int permission_id PK
    }
```

`get_current_user` loads `users → user_roles → roles → role_permissions → permissions`
and flattens the result into `user.permission_codes`. The guard then checks one code
against that set — it never trusts roles or permissions from the JWT.
