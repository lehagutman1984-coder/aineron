from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class DBCredentials:
    host: str
    port: int
    dbname: str
    user: str
    password: str        # в transit; при хранении — Fernet-шифрование
    schema: str | None   # для schema-per-project (Mode 1)
    provider: str        # "aineron" | "neon" | "external" | "timeweb"


class DatabaseProvider(ABC):
    @abstractmethod
    def provision(self, project_id: str) -> DBCredentials: ...

    @abstractmethod
    def sync_schema(self, credentials: DBCredentials, migrations: list[str]) -> None: ...

    @abstractmethod
    def deprovision(self, project_id: str) -> None: ...


# Sprint 3: CREATE SCHEMA proj_<id> + PgBouncer
class AineronSchemaProvider(DatabaseProvider):
    def provision(self, project_id): raise NotImplementedError("Sprint 3")
    def sync_schema(self, credentials, migrations): raise NotImplementedError
    def deprovision(self, project_id): raise NotImplementedError


# Sprint 3: Neon Management API с user-provided API key (self-serve, без OAuth партнёрства)
# POST https://console.neon.tech/api/v2/projects с Bearer {user_neon_api_key}
class NeonProvider(DatabaseProvider):
    def provision(self, project_id): raise NotImplementedError("Sprint 3")
    def sync_schema(self, credentials, migrations): raise NotImplementedError
    def deprovision(self, project_id): raise NotImplementedError


# Sprint 3: connection string от пользователя + Fernet-шифрование
class ExternalProvider(DatabaseProvider):
    def provision(self, project_id): raise NotImplementedError("Sprint 3")
    def sync_schema(self, credentials, migrations): raise NotImplementedError
    def deprovision(self, project_id): raise NotImplementedError


# Sprint 4: Timeweb Cloud Databases API (РФ-юрисдикция, 152-ФЗ)
class TimewebProvider(DatabaseProvider):
    def provision(self, project_id): raise NotImplementedError("Sprint 4")
    def sync_schema(self, credentials, migrations): raise NotImplementedError
    def deprovision(self, project_id): raise NotImplementedError
