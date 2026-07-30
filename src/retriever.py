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

        # 向量库
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
