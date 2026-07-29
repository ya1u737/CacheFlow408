import time
import torch
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
from sentence_transformers import CrossEncoder

from src.config import Config


class KnowledgeBase:
    def __init__(self):
        # 向量模型
        self.embedding = OllamaEmbeddings(
            model=Config.EMBEDDING_MODEL
        )

        # 向量库
        self.db = None

        # Cross Encoder Reranker
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f'[RERANK] 设备: {device}')
        self.reranker = CrossEncoder(Config.RERANKER_MODEL, device=device)

    # ==================== 添加文档 ====================
    def add_documents(self, docs):
        if self.db is None:
            self.db = Chroma.from_documents(docs, self.embedding)
        else:
            self.db.add_documents(docs)

    # ==================== Cross Encoder Rerank ====================
    def rerank(self, query, docs):
        candidates = len(docs)
        if candidates == 0:
            return docs

        # 批量构造 (query, doc) 对
        pairs = [(query, d.page_content) for d in docs]

        # 批量评分
        scores = self.reranker.predict(pairs)

        # 按 score 从高到低排序
        scored = list(zip(scores, docs))
        scored.sort(key=lambda x: x[0], reverse=True)

        selected = [doc for _, doc in scored[:Config.FINAL_TOP_K]]
        return selected

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

        # 3️⃣ Cross Encoder Rerank
        t0 = time.time()
        docs = self.rerank(query, docs)
        t_rerank = time.time() - t0

        print(f'[PERF] Retrieval: {t_retrieval:.2f}s | Rerank: {t_rerank:.2f}s | candidates={candidates} | selected={len(docs)}')

        return docs
