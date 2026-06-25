"""
Database provider abstractions for Studio live preview.

Sprint 3 — code-complete, not integration-tested.

DBCredentials carries connection info in-transit. When persisted (Django side)
it is serialized via to_json() and Fernet-encrypted; decrypted only at
connection time inside the db-proxy. Never log the password / connection_uri.
"""
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict


@dataclass
class DBCredentials:
    host: str
    port: int
    dbname: str
    user: str
    password: str        # в transit; при хранении — Fernet-шифрование
    schema: str | None   # для schema-per-project (Mode 1)
    provider: str        # "aineron" | "neon" | "external" | "timeweb"

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, raw: str) -> "DBCredentials":
        data = json.loads(raw)
        return cls(
            host=data["host"],
            port=int(data["port"]),
            dbname=data["dbname"],
            user=data["user"],
            password=data["password"],
            schema=data.get("schema"),
            provider=data["provider"],
        )


class DatabaseProvider(ABC):
    @abstractmethod
    def provision(self, project_id: str) -> DBCredentials: ...

    @abstractmethod
    def sync_schema(self, credentials: DBCredentials, migrations: list[str]) -> None: ...

    @abstractmethod
    def deprovision(self, project_id: str) -> None: ...


# Sprint 4: Timeweb Cloud Databases API (РФ-юрисдикция, 152-ФЗ)
class TimewebProvider(DatabaseProvider):
    def provision(self, project_id): raise NotImplementedError("Sprint 4")
    def sync_schema(self, credentials, migrations): raise NotImplementedError
    def deprovision(self, project_id): raise NotImplementedError
