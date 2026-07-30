from fastapi import FastAPI, UploadFile, File
from fastapi.responses import StreamingResponse
from backend.service import RAGService
from backend.schemas import (
    QueryRequest, QueryResponse, Reference,
    StatusResponse, LoadKnowledgeResponse,
    UploadResponse, ClearResponse
)

app = FastAPI(title="KnowMate RAG API", version="1.0.0")
service = RAGService()


@app.get("/api/status", response_model=StatusResponse)
def get_status():
    return service.get_status()


@app.post("/api/query", response_model=QueryResponse)
def query(req: QueryRequest):
    result = service.query(req.question, req.chat_history, req.mode)
    references = [Reference(**r) for r in result["references"]]
    return QueryResponse(
        answer=result["answer"],
        references=references,
        perf=result["perf"]
    )


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


@app.post("/api/upload", response_model=UploadResponse)
def upload(file: UploadFile = File(...)):
    return service.upload_document(file)


@app.delete("/api/clear", response_model=ClearResponse)
def clear():
    return service.clear()