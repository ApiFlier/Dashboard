from pydantic import BaseModel

class SourceMeta(BaseModel):
    source: str
    generated_at: str
