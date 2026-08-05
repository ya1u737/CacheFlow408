"""查询改写模块：用轻量本地模型把用户问题改写成更利于向量检索的形式。

改写结果只用于检索（embedding / rerank），生成回答仍使用原始问题。
失败 / 超时时自动回退为原问题，不影响主流程。
"""
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import ollama

from src.config import Config

REWRITE_PROMPT = """你是考研408知识库的检索查询改写助手。
用户提出的复习问题可能口语化、含缩写或省略术语，请把它改写为更适合向量检索的形式：
1. 保留问题原意，补充408标准术语和常见同义表达（例如缩写补全全称、口语转书面）；
2. 只输出改写后的查询本身，一段话，不超过80字；
3. 不要回答原问题，不要输出任何多余解释或前缀。

用户问题：{question}
改写后："""


class QueryProcessor:
    """查询改写器。"""

    def __init__(self):
        self.enabled = Config.QUERY_REWRITE_ENABLED
        self.model = Config.QUERY_REWRITE_MODEL
        self.timeout = Config.QUERY_REWRITE_TIMEOUT
        self.client = None
        if self.enabled:
            try:
                self.client = ollama.Client(
                    host=Config.OLLAMA_BASE_URL, timeout=self.timeout
                )
                print(f"[REWRITE] 查询改写已启用: {self.model} (timeout={self.timeout}s)")
            except Exception as e:
                self.enabled = False
                print(f"[REWRITE] 初始化失败，已回退为不改写: {e}")

    def rewrite(self, question: str) -> str:
        """改写问题；任何异常都回退原问题。"""
        if not self.enabled or self.client is None or not question.strip():
            return question
        try:
            resp = self.client.chat(
                model=self.model,
                messages=[{"role": "user", "content": REWRITE_PROMPT.format(question=question)}],
                options={"temperature": 0.0},
                # 每次调用后立即释放模型显存，避免与 7b 生成模型、reranker 抢显存
                keep_alive="0",
            )
            text = (resp.get("message", {}).get("content", "") or "").strip()
            if text:
                return text
        except Exception as e:
            print(f"[REWRITE] 改写失败，使用原问题: {e}")
        return question
