"""RAG 性能追踪功能验证脚本（独立运行，不依赖 pytest）。

运行方式（项目 conda 环境 408rag）：
    conda activate 408rag
    python tests/validate_perf.py

验证内容：
  1. RAGTimer 单元能力（start/end、上下文管理器、流式迭代器、to_dict、log_trace）
  2. service.query / service.query_stream 的接线与输出（mock 检索与生成，不依赖 Ollama）
"""
import io
import json
import os
import sys
import time
from contextlib import redirect_stdout
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.performance import RAGTimer
from src.config import Config

EXPECTED_STAGES = {
    "query_process", "embedding", "vector_search", "rerank",
    "context_build", "prompt_build", "llm_generation", "total",
}


# ==================== RAGTimer 单元验证 ====================

def test_manual_start_end():
    t = RAGTimer()
    t.start("embedding")
    time.sleep(0.01)
    t.end("embedding")
    assert t.get("embedding") > 0, "start/end 应记录耗时"


def test_end_twice_no_accumulate():
    t = RAGTimer()
    t.start("embedding")
    time.sleep(0.005)
    t.end("embedding")
    first = t.get("embedding")
    t.end("embedding")
    assert t.get("embedding") == first, "重复 end 不应重复累计"


def test_context_manager():
    t = RAGTimer()
    with t.step("vector_search"):
        time.sleep(0.01)
    assert t.get("vector_search") > 0, "上下文管理器应记录耗时"


def test_timed_iterable():
    t = RAGTimer()

    def gen():
        for i in range(3):
            time.sleep(0.005)
            yield i

    wrapped = t.timed_iterable("llm_generation", gen())
    assert list(wrapped) == [0, 1, 2], "包装迭代器不应改变内容"
    assert t.get("llm_generation") > 0, "流式迭代器应记录耗时"


def test_to_dict_format():
    t = RAGTimer()
    d = t.to_dict()
    assert set(d.keys()) == EXPECTED_STAGES, f"字段不完整: {sorted(d.keys())}"
    assert d["rerank"] == 0, "未启用 rerank 时应为 0"
    for v in d.values():
        assert isinstance(v, float), "各阶段应为 float"


def test_performance_wrapper():
    t = RAGTimer()
    p = t.performance()
    assert "performance" in p
    assert set(p["performance"].keys()) == EXPECTED_STAGES


def test_log_trace():
    t = RAGTimer()
    t.start("embedding")
    time.sleep(0.001)
    t.end("embedding")
    buf = io.StringIO()
    with redirect_stdout(buf):
        t.log_trace()
    out = buf.getvalue()
    assert "[RAG Trace]" in out
    assert "embedding:\n" in out
    assert "generation:\n" in out, "llm_generation 日志展示名应为 generation"
    assert "total:\n" in out
    assert " s" in out


# ==================== Rerank 逻辑验证（mock 打分器，不加载真实模型） ====================

class FakeReranker:
    def __init__(self, scores):
        self.scores = scores

    def predict(self, pairs, batch_size=32):
        return self.scores


def test_rerank_orders_and_truncates():
    from src.retriever import KnowledgeBase
    kb = object.__new__(KnowledgeBase)
    kb.rerank_enabled = True
    kb.reranker = FakeReranker([0.1, 0.9, 0.5, 0.7, 0.3])
    docs = [
        SimpleNamespace(metadata={}, page_content=f"doc{i}")
        for i in range(5)
    ]
    ranked = kb.rerank("query", docs)
    assert len(ranked) == Config.FINAL_TOP_K, f"应截断到 FINAL_TOP_K={Config.FINAL_TOP_K}"
    assert [d.page_content for d in ranked] == ["doc1", "doc3", "doc2"], "应按分数降序取 Top3"


def test_rerank_disabled_passthrough():
    from src.retriever import KnowledgeBase
    kb = object.__new__(KnowledgeBase)
    kb.rerank_enabled = False
    kb.reranker = None
    docs = [
        SimpleNamespace(metadata={}, page_content="doc0"),
        SimpleNamespace(metadata={}, page_content="doc1"),
    ]
    assert kb.rerank("query", docs) == docs, "未启用时应原样返回"


def test_rerank_timer_stage():
    t = RAGTimer()
    t.start("rerank")
    time.sleep(0.001)
    t.end("rerank")
    assert t.get("rerank") > 0, "启用 rerank 后应记录 rerank 阶段耗时"


# ==================== Service 集成验证（mock 检索 / 生成） ====================

class MockChunk:
    def __init__(self, content):
        self.content = content


class MockKB:
    """模拟真实 retriever：只对 embedding / vector_search 计时，rerank 未启用。"""

    def __init__(self):
        self.search_called = 0
        self.rerank_enabled = False
        self.last_rerank_top_score = None

    def search(self, query, timer=None):
        self.search_called += 1
        if timer:
            timer.start("embedding")
            time.sleep(0.002)
            timer.end("embedding")
            timer.start("vector_search")
            time.sleep(0.002)
            timer.end("vector_search")
            # rerank 未启用：不计时 → performance["rerank"] == 0
        return [
            SimpleNamespace(metadata={"source": "a.md", "page": 1}, page_content="内容A" * 200),
            SimpleNamespace(metadata={"source": "b.md", "page": 2}, page_content="内容B" * 200),
        ]


class MockGenerator:
    def __init__(self):
        self.current_mode = "ollama"

    def switch_mode(self, mode):
        self.current_mode = mode
        return True

    def generate(self, question, context_docs, chat_history, timer=None):
        if timer:
            timer.start("context_build")
            time.sleep(0.001)
            timer.end("context_build")
            timer.start("prompt_build")
            time.sleep(0.001)
            timer.end("prompt_build")

        def stream():
            for i in range(3):
                time.sleep(0.002)
                yield MockChunk(f"token{i}")

        if timer:
            return timer.timed_iterable("llm_generation", stream())
        return stream()


class MockQueryProcessor:
    """记录改写调用并返回改写后的查询。"""

    def __init__(self):
        self.calls = []

    def rewrite(self, question):
        self.calls.append(question)
        return f"[rewritten] {question}"


class MockKB2(MockKB):
    """额外记录检索用的查询。"""

    def __init__(self):
        super().__init__()
        self.last_query = None

    def search(self, query, timer=None):
        self.last_query = query
        return super().search(query, timer=timer)


class MockKB3(MockKB):
    """模拟启用 rerank 的检索器，可配置置信度分数。"""

    def __init__(self, score):
        super().__init__()
        self.rerank_enabled = True
        self.last_rerank_top_score = score


class MockGenerator2(MockGenerator):
    """额外提供 generate_fallback，记录调用次数。"""

    def __init__(self):
        super().__init__()
        self.fallback_called = 0

    def generate_fallback(self, question, chat_history, timer=None):
        self.fallback_called += 1
        if timer:
            timer.start("context_build")
            timer.end("context_build")
            timer.start("prompt_build")
            timer.end("prompt_build")

        def stream():
            for i in range(3):
                time.sleep(0.002)
                yield MockChunk(f"fallback{i}")

        if timer:
            return timer.timed_iterable("llm_generation", stream())
        return stream()


def _make_service():
    from backend.service import RAGService
    svc = object.__new__(RAGService)
    svc.kb = MockKB()
    svc.generator = MockGenerator()
    svc.current_kb = None
    svc.current_docs = []
    svc.current_chunks = 0
    return svc


def test_service_query():
    svc = _make_service()
    buf = io.StringIO()
    with redirect_stdout(buf):
        result = svc.query("什么是进程？", [{"role": "user", "content": "hi"}], mode="ollama")

    assert result["answer"] == "token0token1token2", "回答内容不应被改变"
    assert len(result["references"]) == 2, "引用数量不应被改变"
    assert set(result["perf"].keys()) == {"retrieval", "generation", "total"}, "旧 perf 字段需保留"
    perf = result["performance"]
    assert set(perf.keys()) == EXPECTED_STAGES, f"performance 字段不完整: {sorted(perf.keys())}"
    assert perf["rerank"] == 0
    assert perf["query_process"] >= 0
    assert perf["embedding"] > 0
    assert perf["vector_search"] > 0
    assert perf["context_build"] > 0
    assert perf["prompt_build"] > 0
    assert perf["llm_generation"] > 0
    assert perf["total"] > 0
    assert "[RAG Trace]" in buf.getvalue(), "应打印 [RAG Trace] 日志"


def test_service_query_rewrite_only_for_retrieval():
    svc = _make_service()
    qp = MockQueryProcessor()
    svc.query_processor = qp
    svc.kb = MockKB2()
    buf = io.StringIO()
    with redirect_stdout(buf):
        result = svc.query("原问题", [], mode="ollama")
    assert qp.calls == ["原问题"], "改写应收到原始问题"
    assert svc.kb.last_query == "[rewritten] 原问题", "检索应使用改写后的查询"
    assert result["answer"] == "token0token1token2", "生成仍应基于原始问题"
    assert result["performance"]["query_process"] >= 0


def test_service_fallback_low_confidence():
    svc = _make_service()
    svc.kb = MockKB3(0.1)
    svc.generator = MockGenerator2()
    buf = io.StringIO()
    with redirect_stdout(buf):
        result = svc.query("问题", [], mode="ollama")
    assert result["grounded"] is False, "低置信度应回退纯模型回答"
    assert result["answer"] == "fallback0fallback1fallback2"
    assert result["references"] == [], "回退模式不应有引用"
    assert svc.generator.fallback_called == 1
    assert result["notice"] != ""


def test_service_grounded_high_confidence():
    svc = _make_service()
    svc.kb = MockKB3(0.9)
    buf = io.StringIO()
    with redirect_stdout(buf):
        result = svc.query("问题", [], mode="ollama")
    assert result["grounded"] is True, "高置信度应基于知识库回答"
    assert result["answer"] == "token0token1token2"
    assert len(result["references"]) == 2
    assert result["notice"] == ""


def test_service_query_stream():
    svc = _make_service()
    events = []
    buf = io.StringIO()
    with redirect_stdout(buf):
        for line in svc.query_stream("什么是进程？", mode="ollama"):
            assert line.startswith("data: "), "SSE 行格式应保持不变"
            events.append(json.loads(line[len("data: "):].strip()))

    types = [e["type"] for e in events]
    assert types[0] == "mode", "应先发送模式事件"
    assert events[0]["data"]["grounded"] is True
    assert types[1] == "references"
    assert types[-2] == "performance", "performance 事件应在 done 之前"
    assert types[-1] == "done"
    assert all(t == "token" for t in types[2:-2]), "token 事件应保持原样"
    perf = events[-2]["data"]
    assert set(perf.keys()) == EXPECTED_STAGES
    assert "[RAG Trace]" in buf.getvalue()


def test_api_schema_has_performance():
    from backend.schemas import QueryResponse, Reference
    resp = QueryResponse(
        answer="ok",
        references=[Reference(source="s", page="1", preview="p")],
        perf={"retrieval": 0, "generation": 0, "total": 0},
        performance={"total": 0.0},
    )
    assert resp.performance == {"total": 0.0}
    assert resp.perf == {"retrieval": 0, "generation": 0, "total": 0}


def main():
    tests = [
        test_manual_start_end,
        test_end_twice_no_accumulate,
        test_context_manager,
        test_timed_iterable,
        test_to_dict_format,
        test_performance_wrapper,
        test_log_trace,
        test_rerank_orders_and_truncates,
        test_rerank_disabled_passthrough,
        test_rerank_timer_stage,
        test_service_query,
        test_service_query_rewrite_only_for_retrieval,
        test_service_fallback_low_confidence,
        test_service_grounded_high_confidence,
        test_service_query_stream,
        test_api_schema_has_performance,
    ]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"[PASS] {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"[FAIL] {fn.__name__}: {e}")
        except Exception as e:
            failed += 1
            print(f"[ERROR] {fn.__name__}: {type(e).__name__}: {e}")
    if failed:
        print(f"\n{failed} 项验证失败")
        sys.exit(1)
    print("\n全部验证通过 ✅")


if __name__ == "__main__":
    main()
