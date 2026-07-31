import os
import time
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings

from src.config import Config


class KnowledgeBase:
    def __init__(self):
        # 向量模型
        self.embedding = OllamaEmbeddings(
            model=Config.EMBEDDING_MODEL
        )

        # 向量库（当前会话使用）
        self.db = None

        # [RERANK 已临时关闭] Cross Encoder Reranker
        # 如需重新启用，取消以下注释：
        # import torch
        # from sentence_transformers import CrossEncoder
        # device = "cuda" if torch.cuda.is_available() else "cpu"
        # self.reranker = CrossEncoder(Config.RERANKER_MODEL, device=device)

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

    # ==================== Rerank（已临时关闭）====================
    # 直接返回传入的 docs，不做重排序
    # 重新启用时：取消上方 __init__ 中注释 + 恢复此方法
    def rerank(self, query, docs):
        return docs

    # ==================== 搜索 ====================
    def search(self, query):
        t_total_start = time.time()

        if self.db is None:
            return []

        # 1️⃣ 向量召回
        t0 = time.time()
        docs = self.db.similarity_search(query, k=Config.RETRIEVAL_TOP_K)
        t_retrieval = time.time() - t0
        candidates = len(docs)

        # 3️⃣ Rerank（已临时关闭）
        docs = self.rerank(query, docs)

        print(f'[PERF] Retrieval: {t_retrieval:.2f}s | candidates={candidates} | selected={len(docs)}')

        return docs
