from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import StreamingResponse, JSONResponse
from backend.service import RAGService
from backend.quiz_service import QuizService
from backend import database as chat_db
from backend.schemas import (
    QueryRequest, QueryResponse, Reference,
    StatusResponse, LoadKnowledgeResponse,
    UploadResponse, ClearResponse, ApiKeyRequest,
    QuizGenerateRequest, QuizGenerateResponse,
    QuizCheckRequest, QuizCheckResponse,
)

app = FastAPI(title="CacheFlow408 RAG API", version="1.0.0")
service = RAGService()
quiz_service = QuizService(service.generator)


@app.get("/api/status", response_model=StatusResponse)
def get_status():
    return service.get_status()


@app.post("/api/query", response_model=QueryResponse)
def query(req: QueryRequest):
    try:
        result = service.query(req.question, req.chat_history, req.mode)
        references = [Reference(**r) for r in result["references"]]
        return QueryResponse(
            answer=result["answer"],
            references=references,
            perf=result["perf"],
            performance=result["performance"],
            grounded=result.get("grounded", True),
            retrieval_confidence=result.get("retrieval_confidence"),
            notice=result.get("notice", "")
        )
    except ValueError as e:
        return JSONResponse(status_code=400, content={"detail": str(e)})


@app.post("/api/query_stream")
async def query_stream(req: QueryRequest):
    print(f"[DEBUG] 收到流式请求: question={req.question[:50]}... mode={req.mode}")
    return StreamingResponse(
        service.query_stream(req.question, req.chat_history, req.mode),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@app.post("/api/load_knowledge", response_model=LoadKnowledgeResponse)
def load_knowledge(filename: str):
    return service.load_knowledge(filename)


@app.post("/api/upload")
def upload(file: UploadFile = File(...), ocr: bool = Form(False)):
    result = service.upload_document(file, ocr=ocr)
    if result.get("status") not in ("ok", "needs_ocr"):
        return JSONResponse(status_code=400, content=result)
    return result


@app.delete("/api/clear", response_model=ClearResponse)
def clear():
    return service.clear()


# ==================== DeepSeek API Key（用户自填）====================

@app.post("/api/config/api_key")
def set_api_key(req: ApiKeyRequest):
    """设置/清除 DeepSeek API Key。Key 仅保存在内存，不写入磁盘。"""
    key = (req.api_key or "").strip()
    if not key:
        service.set_api_key("")
        return {
            "status": "ok",
            "api_available": False,
            "message": "已清除 API Key，当前使用本地模式"
        }
    service.set_api_key(key, req.model)
    return {
        "status": "ok",
        "api_available": True,
        "message": "DeepSeek API 已启用"
    }


# ==================== 聊天历史持久化 ====================

@app.get("/api/history")
def get_history(session_id: str):
    messages = chat_db.get_messages(session_id)
    return {"session_id": session_id, "messages": messages}


@app.post("/api/history/save")
def save_history(body: dict):
    session_id = body.get("session_id")
    role = body.get("role")
    content = body.get("content")
    references = body.get("references") or []
    if not all([session_id, role, content]):
        return {"status": "error", "message": "缺少必要字段"}
    chat_db.save_message(session_id, role, content, references)
    return {"status": "ok"}


@app.delete("/api/history")
def delete_history(session_id: str):
    chat_db.delete_session(session_id)
    return {"status": "ok", "message": f"会话 {session_id} 已删除"}


# ==================== AI 出题 ====================

@app.post("/api/quiz/generate", response_model=QuizGenerateResponse)
def quiz_generate(req: QuizGenerateRequest):
    try:
        return quiz_service.generate(req.subject)
    except ValueError as e:
        return JSONResponse(status_code=400, content={"detail": str(e)})


@app.post("/api/quiz/check", response_model=QuizCheckResponse)
def quiz_check(req: QuizCheckRequest):
    try:
        return quiz_service.check(req.question_id, req.user_answer)
    except ValueError as e:
        return JSONResponse(status_code=400, content={"detail": str(e)})
