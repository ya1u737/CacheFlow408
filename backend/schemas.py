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


# ==================== AI 出题 ====================

class QuizGenerateRequest(BaseModel):
    """生成一道选择题；subject 为空时随机学科。"""
    subject: Optional[str] = None


class QuizGenerateResponse(BaseModel):
    question_id: str
    subject: str
    question: str
    options: List[str]
    answer: str
    knowledge_point: str = ""
    analysis: str = ""
    source: str = ""


class QuizCheckRequest(BaseModel):
    question_id: str
    user_answer: str


class QuizCheckResponse(BaseModel):
    correct: bool
    answer: str
    user_answer: str
    analysis: str = ""
