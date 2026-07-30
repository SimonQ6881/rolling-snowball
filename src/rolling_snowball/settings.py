from __future__ import annotations

import getpass
import os
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = ROOT / ".env"
DEFAULT_PGHOST = str(Path.home() / ".local" / "share" / "rolling-snowball" / "postgres" / "run")
DEFAULT_PGPORT = 5432
DEFAULT_PGDATABASE = "rolling_snowball"
DEFAULT_PGUSER = getpass.getuser()


def load_env_file(path: Path = ENV_PATH) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def env_value(name: str, fallback: str | None = None) -> str | None:
    value = os.getenv(name)
    if value:
        return value
    return load_env_file().get(name, fallback)


@dataclass(frozen=True)
class PostgresSettings:
    host: str = DEFAULT_PGHOST
    port: int = DEFAULT_PGPORT
    dbname: str = DEFAULT_PGDATABASE
    user: str = DEFAULT_PGUSER
    password: str | None = None

    @classmethod
    def from_env(cls) -> "PostgresSettings":
        port_raw = env_value("PGPORT", str(DEFAULT_PGPORT))
        return cls(
            host=env_value("PGHOST", DEFAULT_PGHOST) or DEFAULT_PGHOST,
            port=int(port_raw or DEFAULT_PGPORT),
            dbname=env_value("PGDATABASE", DEFAULT_PGDATABASE) or DEFAULT_PGDATABASE,
            user=env_value("PGUSER", DEFAULT_PGUSER) or DEFAULT_PGUSER,
            password=env_value("PGPASSWORD", None),
        )

    def connect_kwargs(self) -> dict[str, object]:
        kwargs: dict[str, object] = {
            "host": self.host,
            "port": self.port,
            "dbname": self.dbname,
            "user": self.user,
        }
        if self.password:
            kwargs["password"] = self.password
        return kwargs
