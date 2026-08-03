import os
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings

from src.config import Config


class KnowledgeBase:
    def __init__(self):
        # 向量模型
        self.embedding = OllamaEmbeddings(
            model=Config.EMBEDDING_MODEL,
            keep_alive=Config.EMBEDDING_KEEP_ALIVE,
        )

        # 向量库（当前会话使用）
        self.db = None

        # Rerank 开关（配置驱动；启用时加载 Cross Encoder）
        self.rerank_enabled = Config.RERANK_ENABLED
        self.reranker = None
        # 最近一次检索的最高重排分数（分级降级门控用）
        self.last_rerank_top_score = None
        if self.rerank_enabled:
            try:
                import torch
                from sentence_transformers import CrossEncoder
                device = "cuda" if torch.cuda.is_available() else "cpu"
                model_kwargs = {}
                if Config.RERANKER_FP16 and device == "cuda":
                    model_kwargs["torch_dtype"] = torch.float16
                self.reranker = CrossEncoder(
                    Config.RERANKER_MODEL, device=device, model_kwargs=model_kwargs
                )
                print(f"[RERANK] Cross Encoder 已启用: {Config.RERANKER_MODEL} (device={device})")
            except Exception as e:
                self.reranker = None
                self.rerank_enabled = False
                print(f"[RERANK] 模型加载失败，已回退为不启用: {e}")

    # ==================== 添加文档 ====================
    def add_documents(self, docs):
        if self.db is None:
            self.db = Chroma.from_documents(docs, self.embedding)
        else:
            self.db.add_documents(docs)

    # ==================== Chroma 持久化 ====================

    def _kb_path(self, kb_name: str) -> str:
        """知识库对应的持久化目录"""
        safe_name = kb_name.replace("/", "_").replace("\\", "_").replace(" ", "_")
        return os.path.join(Config.VECTOR_DB_PATH, safe_name)

    def has_persistent(self, kb_name: str) -> bool:
        """检查知识库是否已持久化"""
        path = self._kb_path(kb_name)
        # Chroma 持久化目录中应包含 chroma.sqlite3
        return os.path.exists(os.path.join(path, "chroma.sqlite3"))

    def save_persistent(self, kb_name: str, docs) -> int:
        """首次构建：解析后保存到持久化目录，返回 chunks 数"""
        path = self._kb_path(kb_name)
        os.makedirs(path, exist_ok=True)
        db = Chroma.from_documents(docs, self.embedding, persist_directory=path)
        # 让当前会话使用这个向量库
        self.db = db
        return len(docs)

    def load_persistent(self, kb_name: str) -> bool:
        """已有缓存：直接加载持久化目录，不做 embedding"""
        path = self._kb_path(kb_name)
        if not os.path.exists(os.path.join(path, "chroma.sqlite3")):
            return False
        self.db = Chroma(
            persist_directory=path,
            embedding_function=self.embedding
        )
        return True

    # ==================== Rerank（Cross Encoder 重排序）====================
    def rerank(self, query, docs):
        """按 query 与各 doc 的相关性分数降序重排，返回 Top FINAL_TOP_K。

        未启用 / 模型加载失败 / 无候选时，原样返回 docs。
        """
        self.last_rerank_top_score = None
        if not self.rerank_enabled or self.reranker is None or not docs:
            return docs

        pairs = [[query, doc.page_content] for doc in docs]
        scores = self.reranker.predict(pairs, batch_size=32)
        if hasattr(scores, "tolist"):
            scores = scores.tolist()
        self.last_rerank_top_score = float(max(scores))

        scored = sorted(
            zip(docs, scores),
            key=lambda x: x[1],
            reverse=True
        )
        return [doc for doc, _ in scored][:Config.FINAL_TOP_K]

    # ==================== 搜索 ====================
    def search(self, query, timer=None, query_embedding=None):
        """向量检索 + 重排序（返回候选 docs）。

        timer: RAGTimer，记录 embedding / vector_search / rerank 三个阶段。
        query_embedding: 预计算的查询向量（评测预向量化时传入，跳过在线 embedding）。
        rerank 未启用时，rerank 阶段保持 0。
        """
        if self.db is None:
            return []
        self.last_rerank_top_score = None

        # 1. Embedding（Query 向量化）
        if query_embedding is None:
            if timer:
                timer.start("embedding")
            query_embedding = self.embedding.embed_query(query)
            if timer:
                timer.end("embedding")
        elif timer:
            # 评测预向量化模式：embedding 耗时在预跑阶段单独记录
            timer.start("embedding")
            timer.end("embedding")

        # 2. Vector Search（Chroma 向量检索）
        if timer:
            timer.start("vector_search")
        docs = self.db.similarity_search_by_vector(
            query_embedding, k=Config.RETRIEVAL_TOP_K
        )
        if timer:
            timer.end("vector_search")
        candidates = len(docs)

        # 3. Rerank（Cross Encoder 重排序）
        if self.rerank_enabled and timer:
            timer.start("rerank")
        docs = self.rerank(query, docs)
        if self.rerank_enabled and timer:
            timer.end("rerank")

        print(
            f"[PERF] Retrieval: candidates={candidates} | selected={len(docs)}"
        )

        return docs
