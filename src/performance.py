import time
from contextlib import contextmanager


class RAGTimer:
    """RAG 链路统一计时工具。

    - start / end：手动计时
    - step()：with 上下文管理器计时
    - timed_iterable()：包装流式迭代器，首次取值时开始、耗尽/异常时结束
      （用于 LLM 流式生成，避免 time.time() 散落在业务代码中）
    - to_dict()：输出统一格式的 stage -> 耗时(s)
    - log_trace()：打印 [RAG Trace] 日志
    """

    # 统一阶段顺序（rerank 未启用时保持 0）
    STAGES = (
        "query_process",
        "embedding",
        "vector_search",
        "rerank",
        "context_build",
        "prompt_build",
        "llm_generation",
        "total",
    )

    # 日志展示名（llm_generation 按需求以 generation 展示）
    LOG_LABELS = {
        "query_process": "query_process",
        "embedding": "embedding",
        "vector_search": "vector_search",
        "rerank": "rerank",
        "context_build": "context_build",
        "prompt_build": "prompt_build",
        "llm_generation": "generation",
        "total": "total",
    }

    def __init__(self):
        self._records = {}
        # total 从计时器创建（请求开始）即开始计时
        self.start("total")

    # ==================== 手动计时 ====================

    def start(self, name):
        self._records[name] = {"start": time.time()}

    def end(self, name):
        rec = self._records.get(name)
        if rec is None:
            return
        if rec.get("start") is None:
            # 已经 end 过，避免重复累计
            return
        rec["cost"] = time.time() - rec["start"]
        rec["start"] = None

    # ==================== 上下文管理器 ====================

    @contextmanager
    def step(self, name):
        self.start(name)
        try:
            yield
        finally:
            self.end(name)

    # ==================== 流式迭代器计时 ====================

    def timed_iterable(self, name, iterable):
        """包装迭代器：首次取值时 start，迭代结束 / 异常时 end。"""

        def _gen():
            self.start(name)
            try:
                for item in iterable:
                    yield item
            finally:
                self.end(name)

        return _gen()

    # ==================== 汇总输出 ====================

    def get(self, name):
        """返回某个阶段耗时（秒）；未开始/未记录返回 0.0。"""
        rec = self._records.get(name)
        if rec is None:
            return 0.0
        return rec.get("cost", 0.0)

    def to_dict(self):
        """统一格式输出：{"query_process":..., "embedding":..., ..., "total":...}"""
        return {
            stage: round(self.get(stage), 3)
            for stage in self.STAGES
        }

    def performance(self):
        """API 响应中的 performance 字段包装。"""
        return {"performance": self.to_dict()}

    def log_trace(self):
        """打印 [RAG Trace] 日志。"""
        print("[RAG Trace]")
        for stage in self.STAGES:
            label = self.LOG_LABELS.get(stage, stage)
            print(f"{label}:\n{self.get(stage):.3f} s")

    def reset(self):
        """重置所有计时记录。"""
        self._records = {}
        self.start("total")
