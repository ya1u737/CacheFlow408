import os
import sys
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from src.config import Config

# Windows GBK 控制台打印 emoji 会报 UnicodeEncodeError，统一改用 UTF-8 输出
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


class AnswerGenerator:
    def __init__(self):
        # ==================== 本地 Ollama ====================
        self.ollama_llm = ChatOllama(
            model=Config.CHAT_MODEL,
            temperature=0.25,
            streaming=True,
            num_ctx=Config.CHAT_NUM_CTX,  # 上下文窗口（8GB 显存建议 8192）
        )

        # ==================== DeepSeek API（自备 Key）====================
        self.api_llm = None
        # 启动时若 .env / 环境变量里已配置 Key，则自动启用云端模式
        startup_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
        if startup_key:
            self.api_llm = self._build_api_llm(startup_key, Config.API_MODEL)
            print("[LLM] 检测到 DEEPSEEK_API_KEY，DeepSeek API 已就绪")

        # 默认模式
        self.current_mode = "api" if self.api_llm else "ollama"

    # ==================== API Key 管理（运行时用户自填）====================
    def _build_api_llm(self, api_key: str, model: str = None):
        """根据用户提供的 Key 构建 DeepSeek ChatOpenAI 实例"""
        return ChatOpenAI(
            model=model or Config.API_MODEL,
            api_key=api_key,
            base_url=Config.API_BASE,
            temperature=0.25,
            streaming=True,
        )

    @property
    def api_available(self) -> bool:
        """云端 API 是否已配置 Key"""
        return self.api_llm is not None

    def set_api_key(self, api_key: str, model: str = None) -> bool:
        """设置/更新 DeepSeek API Key（仅存内存）。传入空值则清除。"""
        key = (api_key or "").strip()
        if not key:
            self.api_llm = None
            if self.current_mode == "api":
                self.current_mode = "ollama"
            print("[LLM] 已清除 DeepSeek API Key")
            return False
        self.api_llm = self._build_api_llm(key, model or Config.API_MODEL)
        print("[LLM] DeepSeek API Key 已设置")
        return True

    def switch_mode(self, mode: str) -> bool:
        """切换模型模式"""
        if mode == "api":
            if self.api_llm is None:
                print("[LLM] DeepSeek API 未启用：请先填写 API Key")
                return False
            self.current_mode = "api"
            print("🔄 已切换到 → DeepSeek API (云端)")
            return True
        elif mode == "ollama":
            self.current_mode = "ollama"
            print("🔄 已切换到 → 本地 Ollama")
            return True
        return False

    def get_llm(self):
        """返回当前使用的 LLM"""
        return self.api_llm if self.current_mode == "api" else self.ollama_llm

    def generate(self, question: str, context_docs, chat_history, timer=None):
        """生成回答（流式）。

        timer: RAGTimer，记录 context_build / prompt_build / llm_generation 三个阶段。
        llm_generation 通过 timed_iterable 包装流，首次取值时开始计时。
        """
        # 构建参考资料文本（只保留 TOP3 个最相关 chunk）
        if timer:
            timer.start("context_build")
        context_text = ""
        top_docs = context_docs[:3]
        for i, doc in enumerate(top_docs):
            source = doc.metadata.get('source', '未知文件')
            page = doc.metadata.get('page', '?')
            context_text += f"[资料{i + 1}]\n来源：{source} 第{page}页\n内容摘要：{doc.page_content[:50]}...\n完整内容：\n{doc.page_content}\n\n"
        if timer:
            timer.end("context_build")

        # 构建历史对话（保留最近8轮）+ Prompt 模板
        if timer:
            timer.start("prompt_build")
        history_text = ""
        for msg in chat_history[-8:]:
            role = "学生" if msg["role"] == "user" else "导师"
            history_text += f"{role}: {msg['content']}\n"

        prompt = Config.PROMPT_TEMPLATE.format(
            chat_history=history_text,
            context=context_text,
            question=question
        )
        if timer:
            timer.end("prompt_build")

        # 使用当前选择的模型生成回答
        llm = self.get_llm()
        stream = llm.stream(prompt)

        # 流式生成计时（首次取值开始，迭代结束/异常停止）
        if timer:
            stream = timer.timed_iterable("llm_generation", stream)
        return stream

    def generate_fallback(self, question: str, chat_history, timer=None):
        """检索置信度不足时的纯模型回答（不依赖知识库，流式）。

        timer: RAGTimer，context_build 置 0，prompt_build / llm_generation 正常计时。
        """
        if timer:
            timer.start("context_build")
            timer.end("context_build")

        if timer:
            timer.start("prompt_build")
        history_text = ""
        for msg in chat_history[-8:]:
            role = "学生" if msg["role"] == "user" else "导师"
            history_text += f"{role}: {msg['content']}\n"
        prompt = Config.FALLBACK_PROMPT.format(
            chat_history=history_text,
            question=question
        )
        if timer:
            timer.end("prompt_build")

        llm = self.get_llm()
        stream = llm.stream(prompt)
        if timer:
            stream = timer.timed_iterable("llm_generation", stream)
        return stream
