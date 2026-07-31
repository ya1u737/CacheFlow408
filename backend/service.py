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
        # 当前知识库状态
        self.current_kb = None          # 知识库名称
        self.current_docs = []          # 已加载文件列表
        self.current_chunks = 0         # chunk 数量

    def load_knowledge(self, filename: str) -> dict:
        """加载预设知识库文件（带 Chroma 持久化缓存）"""
        path = os.path.join(Config.DATA_PATH, filename)
        if not os.path.exists(path):
            return {"status": "error", "message": f"文件不存在: {path}"}

        # 知识库标识 = 文件名去扩展名
        kb_name = os.path.splitext(filename)[0]

        # == 1. 已有持久化缓存 → 直接加载 ==
        if self.kb.has_persistent(kb_name):
            print(f"[KB] 检测到已有向量库，直接加载: {kb_name}")
            loaded = self.kb.load_persistent(kb_name)
            if loaded:
                chunks = self.kb.db._collection.count()
                # 记录当前知识库状态
                self.current_kb = kb_name
                self.current_docs = [filename]
                self.current_chunks = chunks
                return {
                    "status": "ok",
                    "loaded_from_cache": True,
                    "chunks": chunks,
                    "source": filename
                }

        # == 2. 首次构建 ==
        print(f"[KB] 首次构建知识库，正在生成向量...: {kb_name}")
        docs = self.parser.parse(path)
        if not docs:
            return {"status": "error", "message": "解析结果为空"}

        chunks = self.kb.save_persistent(kb_name, docs)
        print(f"[KB] 生成完成，共 {chunks} 个 chunks")

        # 记录当前知识库状态
        self.current_kb = kb_name
        self.current_docs = [filename]
        self.current_chunks = chunks

        return {
            "status": "ok",
            "loaded_from_cache": False,
            "chunks": chunks,
            "source": filename
        }

    def upload_document(self, file) -> dict:
        """上传并解析文档"""
        ext = os.path.splitext(file.filename)[1].lower()

        # 空文件检验
        if file.size is not None and file.size == 0:
            return {"status": "error", "message": "文件为空，请上传有效文件"}

        # 文件类型校验 + parser 异常捕获
        try:
            if ext == ".pdf":
                docs = self.parser.parse_pdf(file.file)
            elif ext in (".txt", ".md"):
                docs = self.parser.parse_txt(file.file)
            elif ext == ".docx":
                docs = self.parser.parse_docx(file.file)
            else:
                return {"status": "error", "message": f"暂不支持该文件格式 (.{ext})"}
        except ValueError as e:
            return {"status": "error", "message": str(e)}
        except Exception:
            return {"status": "error", "message": "文件解析失败"}

        if not docs:
            return {"status": "error", "message": "文件解析结果为空，请检查文件内容"}

        self.kb.add_documents(docs)
        # 记录当前知识库状态（追加文件到列表）
        self.current_kb = self.current_kb or "上传文件"
        if file.filename not in self.current_docs:
            self.current_docs.append(file.filename)
        self.current_chunks += len(docs)
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

        # 构建引用（只保留 TOP3 + 前50字摘要）
        references = []
        for doc in docs[:3]:
            references.append({
                "source": doc.metadata.get("source", "未知"),
                "page": doc.metadata.get("page", "N/A"),
                "preview": doc.page_content[:150]
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

        # 先发送引用信息（只保留 TOP3 + 前50字摘要）
        references = []
        for doc in docs[:3]:
            references.append({
                "source": doc.metadata.get("source", "未知"),
                "page": doc.metadata.get("page", "N/A"),
                "preview": doc.page_content[:150]
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
            "has_knowledge": self.kb.db is not None,
            "knowledge_base": self.current_kb,
            "documents": self.current_docs,
            "chunk_count": self.current_chunks
        }

    def clear(self) -> dict:
        """清空知识库"""
        self.kb.db = None
        # 重置当前知识库状态
        self.current_kb = None
        self.current_docs = []
        self.current_chunks = 0
        return {"status": "ok", "message": "知识库已清空"}
