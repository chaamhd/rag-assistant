from psycopg.conninfo import make_conninfo
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    postgres_user: str
    postgres_password: SecretStr
    postgres_db: str
    postgres_host: str = "localhost"  # surchargé par "db" dans docker-compose
    postgres_port: int = 5432

    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = 384

    @property
    def database_dsn(self) -> str:
        return make_conninfo(
            host=self.postgres_host,
            port=str(self.postgres_port),
            dbname=self.postgres_db,
            user=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
        )


settings = Settings()