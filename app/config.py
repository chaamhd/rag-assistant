from typing import Literal
from psycopg.conninfo import make_conninfo
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Base de données
    postgres_user: str
    postgres_password: SecretStr
    postgres_db: str
    postgres_host: str 
    postgres_port: int = Field(gt=0, lt=65536)

    # Embeddings 
    embedding_model: str
    embedding_dim: int = Field(gt=0)

    # Modèle de langage 
    llm_base_url: str
    llm_api_key: SecretStr 
    llm_model: str 

    # Recherche et génération
    search_top_k: int = Field(gt=0)
    search_mode: Literal["vector", "hybrid"]  
    search_candidates: int = Field(gt=0)     
    rrf_k: int = Field(gt=0)                 
    fts_language: str = Field(pattern=r"^[a-z_]+$")
    rerank_enabled: bool                       
    rerank_model: str                          
    rerank_candidates: int = Field(gt=0)       
    llm_temperature: float = Field(ge=0, le=2)
    llm_timeout_seconds: float = Field(gt=0)
    llm_max_retries: int = Field(ge=0)

    # API
    question_max_chars: int = Field(gt=0)

    # Journalisation
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"]

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