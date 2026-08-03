import os
import json
from src.parser import DocumentParser
from src.retriever import KnowledgeBase
from src.generator import AnswerGenerator
from src.config import Config
from src.performance import RAGTimer
from src.query_processor import QueryProcessor


class RAGService:
    def __init__(self):
        self.parser = DocumentParser()
        self.kb = KnowledgeBase()
        self.generator = AnswerGenerator()
        self.query_processor = QueryProcessor() if Config.QUERY_REWRITE_ENABLED else None
        # 当前知识库状态
        self.current_kb = None          # 知识库名称
        self.current_docs = []          # 已加载文件列表
        self.current_chunks = 0         # chunk 数量

    def set_api_key(self, api_key: str, model: str = None) -> bool:
        """设置 DeepSeek API Key（用户自填，仅存内存）"""
        return self.generator.set_api_key(api_key, model)

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

        timer = RAGTimer()
        answer = ""
        references = []
        try:
            # 1. query_process：用户问题预处理
            timer.start("query_process")
            mode_ok = self.generator.switch_mode(mode)
            rewritten = question
            if getattr(self, "query_processor", None) is not None:
                rewritten = self.query_processor.rewrite(question)
            timer.end("query_process")
            # 请求云端但未配置 Key：明确报错，避免静默回退到本地模型
            if mode == "api" and not mode_ok:
                raise ValueError("DeepSeek API 模式未启用，请先在侧边栏填写 API Key")

            # 2. 检索（embedding / vector_search / rerank 在 retriever 内计时）
            docs = self.kb.search(rewritten, timer=timer)

            # 2.5 分级降级：检索置信度不足时回退纯模型回答（避免错误上下文带偏答案）
            grounded, confidence = self._retrieval_gate(docs)

            # 3. 生成回答（context_build / prompt_build / llm_generation 在 generator 内计时）
            if grounded:
                stream = self.generator.generate(question, docs, chat_history, timer=timer)
            else:
                stream = self.generator.generate_fallback(question, chat_history, timer=timer)
            for chunk in stream:
                content = chunk.content if hasattr(chunk, "content") else str(chunk)
                answer += content

            # 4. 构建引用（只保留 TOP3 + 前50字摘要）
            if grounded:
                for doc in docs[:3]:
                    references.append({
                        "source": doc.metadata.get("source", "未知"),
                        "page": doc.metadata.get("page", "N/A"),
                        "preview": doc.page_content[:150]
                    })
        finally:
            # 5. total：完整请求耗时 + [RAG Trace] 日志
            timer.end("total")
            timer.log_trace()

        perf = timer.to_dict()
        return {
            "answer": answer,
            "references": references,
            # 分级降级：检索是否可信 + 最高重排分 + 回退提示
            "grounded": grounded,
            "retrieval_confidence": confidence,
            "notice": "" if grounded else Config.FALLBACK_NOTICE,
            # 保留旧的 perf 字段（向后兼容）
            "perf": {
                "retrieval": round(perf["embedding"] + perf["vector_search"] + perf["rerank"], 2),
                "generation": round(perf["llm_generation"], 2),
                "total": round(perf["total"], 2)
            },
            # 新增 performance 字段
            "performance": perf
        }

    def _retrieval_gate(self, docs):
        """分级降级门控：返回 (grounded, confidence)。

        grounded=True：检索置信度足够，基于知识库回答；
        grounded=False：没有候选或置信度不足，回退纯模型回答。
        """
        if not docs:
            return False, None
        if not Config.RAG_FALLBACK_ENABLED or not self.kb.rerank_enabled:
            return True, None
        confidence = getattr(self.kb, "last_rerank_top_score", None)
        if confidence is None or confidence < Config.RAG_FALLBACK_THRESHOLD:
            return False, confidence
        return True, confidence

    def query_stream(self, question: str, chat_history: list = None, mode: str = "ollama"):
        """流式 RAG 流程 — 用于 SSE 接口"""
        if chat_history is None:
            chat_history = []

        timer = RAGTimer()
        try:
            # 1. query_process：用户问题预处理
            timer.start("query_process")
            mode_ok = self.generator.switch_mode(mode)
            rewritten = question
            if getattr(self, "query_processor", None) is not None:
                rewritten = self.query_processor.rewrite(question)
            timer.end("query_process")
            # 请求云端但未配置 Key：通过 SSE error 事件明确提示
            if mode == "api" and not mode_ok:
                yield f"data: {json.dumps({'type': 'error', 'data': 'DeepSeek API 模式未启用，请先在侧边栏填写 API Key'})}\n\n"
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                return

            # 2. 检索 + 生成（分阶段计时在 retriever / generator 内完成）
            docs = self.kb.search(rewritten, timer=timer)
            grounded, confidence = self._retrieval_gate(docs)
            if grounded:
                stream = self.generator.generate(question, docs, chat_history, timer=timer)
            else:
                stream = self.generator.generate_fallback(question, chat_history, timer=timer)

            # 先发送模式事件（前端可据此展示"知识库未命中"提示）
            yield f"data: {json.dumps({'type': 'mode', 'data': {'grounded': grounded, 'confidence': confidence, 'notice': '' if grounded else Config.FALLBACK_NOTICE}})}\n\n"

            # 先发送引用信息（只保留 TOP3 + 前50字摘要）
            references = []
            if grounded:
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
        finally:
            # total：完整请求耗时（含流式生成）+ [RAG Trace] 日志
            timer.end("total")
            timer.log_trace()

        # 性能追踪事件（放在 done 之前；前端对未知类型直接忽略，保持 SSE 兼容）
        yield f"data: {json.dumps({'type': 'performance', 'data': timer.to_dict()})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    def get_status(self) -> dict:
        """返回服务状态"""
        return {
            "status": "running",
            "mode": self.generator.current_mode,
            "model": Config.CHAT_MODEL,
            "embedding": Config.EMBEDDING_MODEL,
            "has_knowledge": self.kb.db is not None,
            "api_available": self.generator.api_available,
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
