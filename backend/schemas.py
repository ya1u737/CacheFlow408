from pydantic import BaseModel
from typing import List, Optional


class QueryRequest(BaseModel):
    question: str
    chat_history: Optional[List[dict]] = []
    mode: str = "ollama"


class Reference(BaseModel):
    source: str
    page: str
    preview: str
    model_config = {
        "coerce_numbers_to_str": True
    }

class QueryResponse(BaseModel):
    answer: str
    references: List[Reference]
    perf: dict


class StatusResponse(BaseModel):
    status: str
    mode: str
    model: str
    embedding: str
    has_knowledge: bool


class LoadKnowledgeResponse(BaseModel):
    status: str
    chunks: Optional[int] = None
    source: Optional[str] = None
    message: Optional[str] = None


class UploadResponse(BaseModel):
    status: str
    chunks: Optional[int] = None
    source: Optional[str] = None
    message: Optional[str] = None


class ClearResponse(BaseModel):
    status: str
    message: str