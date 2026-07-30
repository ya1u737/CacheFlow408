import os
import time
import json
from src.parser import DocumentParser
from src.retriever import KnowledgeBase
from src.generator import AnswerGenerator
from src.config import Config


class RAGService:
    def __init__(self):
        self.parser = DocumentParser()
        self.kb = KnowledgeBase()
        self.generator = AnswerGenerator()

    def load_knowledge(self, filename: str) -> dict:
        """加载预设知识库文件"""
        path = os.path.join(Config.DATA_PATH, filename)
        if not os.path.exists(path):
            return {"status": "error", "message": f"文件不存在: {path}"}

        docs = self.parser.parse(path)
        if not docs:
            return {"status": "error", "message": "解析结果为空"}

        self.kb.add_documents(docs)
        return {"status": "ok", "chunks": len(docs), "source": filename}

    def upload_document(self, file) -> dict:
        """上传并解析文档"""
        ext = os.path.splitext(file.filename)[1].lower()

        if ext == ".pdf":
            docs = self.parser.parse_pdf(file.file)
        elif ext in (".txt", ".md"):
            docs = self.parser.parse_txt(file.file)
        elif ext == ".docx":
            docs = self.parser.parse_docx(file.file)
        else:
            return {"status": "error", "message": f"不支持的文件类型: {ext}"}

        if not docs:
            return {"status": "error", "message": "解析结果为空"}

        self.kb.add_documents(docs)
        return {"status": "ok", "chunks": len(docs), "source": file.filename}

    def query(self, question: str, chat_history: list = None, mode: str = "ollama") -> dict:
        """执行完整 RAG 流程"""
        if chat_history is None:
            chat_history = []

        t0 = time.time()

        # 切换模式
        self.generator.switch_mode(mode)

        # 检索
        t1 = time.time()
        docs = self.kb.search(question)
        t_retrieval = time.time() - t1

        # 生成回答
        t2 = time.time()
        stream = self.generator.generate(question, docs, chat_history)
        answer = ""
        for chunk in stream:
            content = chunk.content if hasattr(chunk, "content") else str(chunk)
            answer += content
        t_generation = time.time() - t2

        t_total = time.time() - t0

        # 构建引用
        references = []
        for doc in docs:
            references.append({
                "source": doc.metadata.get("source", "未知"),
                "page": doc.metadata.get("page", "N/A"),
                "preview": doc.page_content[:100]
            })

        return {
            "answer": answer,
            "references": references,
            "perf": {
                "retrieval": round(t_retrieval, 2),
                "generation": round(t_generation, 2),
                "total": round(t_total, 2)
            }
        }

    def query_stream(self, question: str, chat_history: list = None, mode: str = "ollama"):
        """流式 RAG 流程 — 用于 SSE 接口"""
        if chat_history is None:
            chat_history = []

        self.generator.switch_mode(mode)

        docs = self.kb.search(question)
        stream = self.generator.generate(question, docs, chat_history)

        # 先发送引用信息
        references = []
        for doc in docs:
            references.append({
                "source": doc.metadata.get("source", "未知"),
                "page": doc.metadata.get("page", "N/A"),
                "preview": doc.page_content[:100]
            })

        yield f"data: {json.dumps({'type': 'references', 'data': references})}\n\n"

        # 逐 token 发送
        for chunk in stream:
            content = chunk.content if hasattr(chunk, "content") else str(chunk)
            yield f"data: {json.dumps({'type': 'token', 'data': content})}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    def get_status(self) -> dict:
        """返回服务状态"""
        return {
            "status": "running",
            "mode": self.generator.current_mode,
            "model": Config.CHAT_MODEL,
            "embedding": Config.EMBEDDING_MODEL,
            "has_knowledge": self.kb.db is not None
        }

    def clear(self) -> dict:
        """清空知识库"""
        self.kb.db = None
        return {"status": "ok", "message": "知识库已清空"}