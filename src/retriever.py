import os
import math
import re
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings

from src.config import Config


_CJK_RE = re.compile(r"[\u4e00-\u9fff]+")
_WORD_RE = re.compile(r"[a-z0-9]+")


def tokenize(text):
    """中文按字 + 双字二元组切词，英文/数字按词切分（BM25 用）。"""
    text = (text or "").lower()
    tokens = []
    for m in _WORD_RE.finditer(text):
        tokens.append(m.group(0))
    for seg in _CJK_RE.findall(text):
        n = len(seg)
        if n == 1:
            tokens.append(seg)
        else:
            tokens.extend(list(seg))
            tokens.extend(seg[i:i + 2] for i in range(n - 1))
    return tokens


class BM25Okapi:
    """轻量 BM25（k1=1.5, b=0.75），无需第三方依赖。"""

    def __init__(self, corpus):
        self.k1 = 1.5
        self.b = 0.75
        self.corpus_size = len(corpus)
        self.avgdl = (
            sum(len(d) for d in corpus) / self.corpus_size if self.corpus_size else 0.0
        )
        self.doc_len = [len(d) for d in corpus]
        self.doc_freqs = []
        df = {}
        for toks in corpus:
            tf = {}
            for t in toks:
                tf[t] = tf.get(t, 0) + 1
            self.doc_freqs.append(tf)
            for t in set(toks):
                df[t] = df.get(t, 0) + 1
        self.idf = {
            t: math.log(1 + (self.corpus_size - f + 0.5) / (f + 0.5))
            for t, f in df.items()
        }

    def get_scores(self, query):
        scores = [0.0] * self.corpus_size
        if not self.corpus_size or not self.avgdl:
            return scores
        for q in set(query):
            qidf = self.idf.get(q)
            if qidf is None:
                continue
            for i, tf in enumerate(self.doc_freqs):
                freq = tf.get(q)
                if not freq:
                    continue
                denom = freq + self.k1 * (
                    1 - self.b + self.b * self.doc_len[i] / self.avgdl
                )
                scores[i] += qidf * freq * (self.k1 + 1) / denom
        return scores

    def get_top_n(self, query, documents, n=10):
        scores = self.get_scores(query)
        order = sorted(
            range(len(scores)), key=lambda i: scores[i], reverse=True
        )
        return [documents[i] for i in order[:n] if scores[i] > 0]


class KnowledgeBase:
    def __init__(self):
        # 向量模型
        self.embedding = OllamaEmbeddings(
            model=Config.EMBEDDING_MODEL,
            keep_alive=Config.EMBEDDING_KEEP_ALIVE,
        )

        # 向量库（当前会话使用）
        self.db = None

        # 混合检索（BM25 + RRF）
        self.hybrid_enabled = Config.HYBRID_ENABLED
        self.bm25 = None
        self._chunk_docs = []
        self._bm25_ready = False

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
        self._build_bm25_index()

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
        self._build_bm25_index()
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
        self._build_bm25_index()
        return True

    # ==================== BM25 索引 ====================
    def _build_bm25_index(self):
        """从当前向量库的 chunk 文本构建 BM25 词法索引（失败时静默回退纯向量）。"""
        self.bm25 = None
        self._chunk_docs = []
        self._bm25_ready = False
        if not self.hybrid_enabled or self.db is None:
            return
        try:
            data = self.db.get(include=["documents", "metadatas"])
            texts = data.get("documents") or []
            metas = data.get("metadatas") or []
            self._chunk_docs = [
                Document(page_content=t, metadata=m)
                for t, m in zip(texts, metas)
            ]
            if not self._chunk_docs:
                return
            self.bm25 = BM25Okapi([tokenize(t) for t in texts])
            self._bm25_ready = True
            print(
                f"[HYBRID] BM25 索引就绪: {len(self._chunk_docs)} chunks"
            )
        except Exception as e:
            self._bm25_ready = False
            print(f"[HYBRID] BM25 索引构建失败，回退纯向量检索: {e}")

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

        # 2. 混合检索（向量 + BM25 + RRF 融合；失败时自动回退纯向量）
        if timer:
            timer.start("vector_search")
        docs = self._hybrid_search(query, query_embedding)
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

    def _hybrid_search(self, query, query_embedding):
        """向量 top-N 与 BM25 top-N 做 RRF 融合，返回 Top RETRIEVAL_TOP_K 候选。"""
        dense_docs = self.db.similarity_search_by_vector(
            query_embedding, k=Config.DENSE_TOP_K
        )
        if not self.hybrid_enabled or not self._bm25_ready or not self.bm25:
            return dense_docs[: Config.RETRIEVAL_TOP_K]

        try:
            bm25_docs = self.bm25.get_top_n(
                tokenize(query), self._chunk_docs, n=Config.BM25_TOP_K
            )
        except Exception as e:
            print(f"[HYBRID] BM25 检索失败，回退纯向量: {e}")
            return dense_docs[: Config.RETRIEVAL_TOP_K]

        rrf_scores = {}
        for rank, doc in enumerate(dense_docs, 1):
            rrf_scores[doc.page_content] = (
                rrf_scores.get(doc.page_content, 0.0)
                + Config.RRF_DENSE_WEIGHT / (Config.RRF_K + rank)
            )
        for rank, doc in enumerate(bm25_docs, 1):
            rrf_scores[doc.page_content] = (
                rrf_scores.get(doc.page_content, 0.0)
                + Config.RRF_BM25_WEIGHT / (Config.RRF_K + rank)
            )

        doc_by_content = {}
        for d in dense_docs:
            doc_by_content[d.page_content] = d
        for d in bm25_docs:
            doc_by_content[d.page_content] = d

        merged = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        return [
            doc_by_content[content]
            for content, _ in merged[: Config.RETRIEVAL_TOP_K]
        ]
