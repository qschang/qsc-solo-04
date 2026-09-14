from dataclasses import dataclass
import os

@dataclass(frozen=True)
class Settings:
    database_path: str = "data/surveyops.sqlite3"
    bind_host: str = "127.0.0.1"
    bind_port: int = 8080
    max_batch_size: int = 100
    checkpoint_interval: int = 5
    role_catalog: tuple = ("operator", "scientist", "auditor")

    @classmethod
    def from_env(cls):
        return cls(
            database_path=os.getenv("SURVEYOPS_DB", cls.database_path),
            bind_host=os.getenv("SURVEYOPS_HOST", cls.bind_host),
            bind_port=int(os.getenv("SURVEYOPS_PORT", str(cls.bind_port))),
            max_batch_size=int(os.getenv("SURVEYOPS_MAX_BATCH", str(cls.max_batch_size))),
            checkpoint_interval=int(os.getenv("SURVEYOPS_CHECKPOINT_INTERVAL", str(cls.checkpoint_interval))),
        )
