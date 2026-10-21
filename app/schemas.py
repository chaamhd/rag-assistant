from pydantic import BaseModel, ConfigDict, Field

from app.config import settings


class AskRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    question: str = Field(min_length=1, max_length=settings.question_max_chars)