from datetime import datetime
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
