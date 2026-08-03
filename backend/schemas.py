from pydantic import BaseModel
from typing import List, Optional


class QueryRequest(BaseModel):
    question: str
    chat_history: Optional[List[dict]] = []
    mode: str = "ollama"


class ApiKeyRequest(BaseModel):
    """用户自填 DeepSeek API Key"""
    api_key: str
    model: Optional[str] = None


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
    performance: dict = {}
    grounded: bool = True
    retrieval_confidence: Optional[float] = None
    notice: str = ""


class StatusResponse(BaseModel):
    status: str
    mode: str
    model: str
    embedding: str
    has_knowledge: bool
    api_available: bool = False
    knowledge_base: Optional[str] = None
    documents: List[str] = []
    chunk_count: int = 0


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
