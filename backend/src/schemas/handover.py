from pydantic import BaseModel, Field


class HandoverInput(BaseModel):
    label: str = Field(default='', max_length=160)
