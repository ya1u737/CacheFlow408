from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from src.config import Config


class AnswerGenerator:
    def __init__(self):
        # ==================== 本地 Ollama ====================
        self.ollama_llm = ChatOllama(
            model=Config.CHAT_MODEL,
            temperature=0.25,
            streaming=True,
            num_ctx=16384,  # 上下文窗口
        )

        # ==================== DeepSeek API ====================
        self.api_llm = None
        
        # 默认模式
        self.current_mode = "api" if self.api_llm else "ollama"

    def switch_mode(self, mode: str) -> bool:
        """切换模型模式"""
        if mode == "api" and self.api_llm is not None:
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

    def generate(self, question: str, context_docs, chat_history):
        # 构建参考资料文本
        context_text = ""
        for i, doc in enumerate(context_docs):
            source = doc.metadata.get('source', '未知文件')
            page = doc.metadata.get('page', '?')
            context_text += f"[片段 {i + 1} | 来源: {source} 第{page}页]\n{doc.page_content}\n\n"

        # 构建历史对话（保留最近8轮）
        history_text = ""
        for msg in chat_history[-8:]:
            role = "学生" if msg["role"] == "user" else "导师"
            history_text += f"{role}: {msg['content']}\n"

        prompt = Config.PROMPT_TEMPLATE.format(
        chat_history=history_text,
        context=context_text,
        question=question
    )

        # 使用当前选择的模型生成回答
        llm = self.get_llm()
        return llm.stream(prompt)