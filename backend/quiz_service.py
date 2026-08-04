"""AI 出题服务：题库随机选题 + 答案判定 + 答题校验。

设计（与用户确认）：
- 从清洗好的题库随机选题，答案优先用题库自带的（保证正确）；
- 操作系统题库绝大多数没有答案，由本地 LLM（Ollama）判题，判题结果做缓存；
- 暂不生成解析（接口保留 analysis 空字段，后续扩展不用改前端）；
- 判题前用该题文本检索知识点库做 grounding，提高本地模型准确率；
- 复用现有 retriever / generator，不影响聊天链路。
"""

import json
import os
import random
import re

from src.config import Config
from src.quiz_bank import QuizBank
from src.retriever import KnowledgeBase


JUDGE_PROMPT = """你是一名408计算机考研阅卷老师。请判断下面这道单选题的正确选项，只输出一个答案字母。
要求：只输出一行，格式为：答案：X（X 为 A/B/C/D 之一），不要输出其他内容。

{context}

题目：{question}

选项：
{options}
"""


class QuizService:
    def __init__(self, generator):
        self.bank = QuizBank()
        # 复用主服务的生成器（含 Ollama / DeepSeek 切换与 API Key）
        self.generator = generator
        # 判题 grounding 用独立检索实例：关闭 rerank，不占 reranker 显存、不动聊天库
        self.kb = KnowledgeBase(rerank_enabled=False)
        self._kb_loaded = None
        self._os_answers = self._load_answer_cache()

    # ==================== 对外接口 ====================

    def generate(self, subject=None):
        subject = subject or random.choice(self.bank.subjects())
        if subject not in self.bank.subjects():
            raise ValueError(f"未知学科: {subject}")
        q = self.bank.random_pick(subject)
        if q is None:
            raise ValueError(f"学科「{subject}」暂无可用题目")
        answer = q["answer"]
        if answer is None:
            answer = self._judge_answer(q)
        return {
            "question_id": q["id"],
            "subject": subject,
            "question": q["question"],
            "options": q["options"],
            "answer": answer,
            "knowledge_point": q.get("knowledge_point") or "",
            "analysis": "",
            "source": q.get("source", ""),
        }

    def check(self, question_id, user_answer):
        q = self.bank.get(question_id)
        if q is None:
            raise ValueError(f"题目不存在: {question_id}")
        answer = q["answer"]
        if answer is None:
            answer = self._judge_answer(q)
        ua = (user_answer or "").strip().upper()
        return {
            "correct": ua == answer.upper(),
            "answer": answer,
            "user_answer": ua or (user_answer or ""),
            "analysis": "",
        }

    # ==================== 操作系统判题 ====================

    def _judge_answer(self, q):
        qid = q["id"]
        if qid in self._os_answers:
            return self._os_answers[qid]
        answer = self._ask_llm(q)
        if answer:
            self._os_answers[qid] = answer
            self._save_answer_cache()
        else:
            raise ValueError(f"本地模型判题失败: {qid}")
        return answer

    def _ask_llm(self, q):
        context = ""
        if Config.QUIZ_GROUNDING_ENABLED:
            context = self._grounding(q)
        prompt = JUDGE_PROMPT.format(
            context=context or "（未检索到参考资料）",
            question=q["question"],
            options="\n".join(q["options"]),
        )
        llm = self.generator.ollama_llm  # 按用户要求：操作系统判题固定用本地模型
        for attempt in range(2):
            try:
                resp = llm.invoke(prompt)
                text = resp.content if hasattr(resp, "content") else str(resp)
                m = re.search(r"答案[：:]\s*([A-D])", text)
                if not m:
                    m = re.search(r"[A-D](?=。|\s|$)", text)
                if m:
                    return m.group(1)
                print(f"[QUIZ] 判题输出无法解析: {text[:120]!r}")
            except Exception as e:
                print(f"[QUIZ] 判题调用失败（第{attempt + 1}次）: {type(e).__name__}: {e}")
        return None

    def _grounding(self, q):
        kb_name = f"{q['subject']}_知识点"
        try:
            if self._kb_loaded != kb_name:
                if not self.kb.load_persistent(kb_name):
                    return ""
                self._kb_loaded = kb_name
            docs = self.kb.search(q["question"])
        except Exception as e:
            print(f"[QUIZ] grounding 检索失败: {type(e).__name__}: {e}")
            return ""
        parts = []
        for i, doc in enumerate(docs[:3], 1):
            parts.append(f"[资料{i}] {doc.page_content[:400]}")
        return "\n\n".join(parts)

    # ==================== 判题结果缓存 ====================

    def _cache_path(self):
        return Config.QUIZ_ANSWER_CACHE_PATH

    def _load_answer_cache(self):
        path = self._cache_path()
        if not os.path.exists(path):
            return {}
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except Exception as e:
            print(f"[QUIZ] 判题缓存读取失败: {e}")
        return {}

    def _save_answer_cache(self):
        try:
            os.makedirs(os.path.dirname(self._cache_path()), exist_ok=True)
            with open(self._cache_path(), "w", encoding="utf-8") as f:
                json.dump(self._os_answers, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[QUIZ] 判题缓存保存失败: {e}")
