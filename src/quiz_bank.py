"""题库解析器：把 data/clean_md 下清洗好的题库 md 解析成结构化选择题池。

四份题库格式实测不一致（2026-08）：
- 数据结构_题库：`### 第N题` + `**题目**：` / `**选项**：D. x | C. y | A. z | B. w`（选项乱序）
- 组成原理_题库：`## 第N题` + `### 题目` + 裸排 A. B. C. D. + `### 答案`（混有简答/计算，需过滤）
- 计算机网络_题库：`## 第N题` + `### 题目` + `### 选项`（四选项挤在同一行）+ `### 答案`
- 操作系统_题库：`## 第N题` + `### 题目` + `### 选项`（绝大多数题没有答案，由本地 LLM 判题）

产物：subject -> Question，Question = {
    id, subject, question, options[4], answer(A-D 或 None), knowledge_point, source
}
"""

import os
import random
import re

from src.config import Config


SUBJECT_FILES = {
    "数据结构": "数据结构_题库.md",
    "操作系统": "操作系统_题库.md",
    "组成原理": "组成原理_题库.md",
    "计算机网络": "计算机网络_题库.md",
}

# 题目块头：`## 第N题` / `### 第N题`
_HEADER_RE = re.compile(r"^#{2,3} 第(\d+)题\s*$", re.M)

# 题干/选项中的水印残留
_WATERMARK = re.compile(r"公众号|祝您上岸|顶尖考研|扫码|二维码|获取更多|微信")

# 题干末尾被粘连的选项碎片，如 "计算机网络最基本的功能是（）。 C．分布式处理"
_TRAILING_OPT = re.compile(r"[A-D][.．、]\s*[^。\n]{1,40}$")


class QuizBank:
    """解析并持有四科题库的选择题池（纯标准库，无外部依赖）。"""

    def __init__(self):
        self._pool = {}      # subject -> [question]
        self._by_id = {}     # question_id -> question
        for subject in SUBJECT_FILES:
            self._parse_subject(subject)

    # ==================== 对外接口 ====================

    def subjects(self):
        return list(SUBJECT_FILES)

    def pool_size(self, subject):
        return len(self._pool.get(subject, []))

    def random_pick(self, subject):
        pool = self._pool.get(subject) or []
        return random.choice(pool) if pool else None

    def get(self, question_id):
        return self._by_id.get(question_id)

    # ==================== 解析 ====================

    def _parse_subject(self, subject):
        path = os.path.join(Config.QUIZ_BANK_DIR, SUBJECT_FILES[subject])
        if not os.path.exists(path):
            print(f"[QUIZ] 题库文件不存在，跳过: {path}")
            self._pool[subject] = []
            return
        with open(path, encoding="utf-8") as f:
            text = f.read()
        matches = list(_HEADER_RE.finditer(text))
        # 一级标题（# 第N章 …）位置：题目编号会随章节重置，id 需带上章节序号
        h1 = [
            (m.start(), i)
            for i, m in enumerate(re.finditer(r"(?m)^# .+$", text), 1)
        ]

        def chapter_index(pos):
            idx = 0
            for p, i in h1:
                if p < pos:
                    idx = i
                else:
                    break
            return idx

        items = []
        seen = set()
        for idx, m in enumerate(matches):
            number = int(m.group(1))
            start = m.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
            q = self._parse_block(subject, number, text[start:end])
            if q:
                q["id"] = f"{subject}-c{chapter_index(start)}-{number}"
                # 兜底：个别文件章节标记异常时保证 id 唯一
                k, n = q["id"], 2
                while k in seen:
                    k = f"{q['id']}-{n}"
                    n += 1
                q["id"] = k
                seen.add(k)
                items.append(q)
        self._pool[subject] = items
        for q in items:
            self._by_id[q["id"]] = q
        print(f"[QUIZ] {subject}: 可用选择题 {len(items)} 道（题库共 {len(matches)} 块）")

    def _parse_block(self, subject, number, block):
        question = self._extract_stem(block)
        options = self._extract_options(block)
        if not question or len(options) != 4:
            return None
        answer = self._extract_answer(block)
        # 操作系统题库绝大多数无答案，交由本地 LLM 判题（answer=None）；
        # 其余三科必须带题库答案，保证正确性。
        if subject != "操作系统" and answer is None:
            return None
        return {
            "id": f"{subject}-{number}",
            "subject": subject,
            "question": question,
            "options": options,
            "answer": answer,
            "knowledge_point": self._extract_knowledge_point(block),
            "source": SUBJECT_FILES[subject],
        }

    def _extract_stem(self, block):
        m = re.search(r"\*\*题目\*\*[：:]\s*([^\n]+)", block)
        if m:
            stem = m.group(1).strip()
        else:
            m = re.search(r"### 题目\s*\n(.*?)(?=\n### |\n## |\n\*\*|\Z)", block, re.S)
            if not m:
                return None
            lines = []
            for line in m.group(1).splitlines():
                s = line.strip()
                if not s or _WATERMARK.search(s):
                    continue
                lines.append(s)
            stem = "".join(lines)
        stem = _TRAILING_OPT.sub("", stem).strip()
        stem = re.sub(r"\s+", " ", stem).strip()
        # 清洗残留：多空题 / 两题被合并到同一块（如 "。。。 C．xxx 06．yyyy（）"）时整题拒绝。
        # 空括号计数排除函数调用写法（F（）、push（）等，字母/数字紧邻括号不算填空）
        blanks = len(re.findall(r"(?<![A-Za-z0-9_])（）", stem))
        if blanks >= 2 or re.search(r"\d+[．]\s*\S", stem):
            return None
        return stem or None

    def _extract_options(self, block):
        region = ""
        m = re.search(r"### 选项\s*\n(.*?)(?=\n### |\n## |\n\*\*|\Z)", block, re.S)
        if m:
            region = m.group(1)
        else:
            m = re.search(r"\*\*选项\*\*[：:]\s*([^\n]+)", block)
            if m:
                region = m.group(1)
            else:
                region = "\n".join(
                    l for l in block.splitlines() if re.match(r"^[A-D][.．、]", l)
                )
        if not region.strip():
            return []
        # 按选项标记切分，兼容 "A. xB. y" 粘连与 "D. x | C. y" 分隔
        parts = re.split(r"(?<![A-Z])([A-D])[.．、]\s*", region)
        opts = {}
        for i in range(1, len(parts) - 1, 2):
            letter = parts[i]
            text = parts[i + 1].strip()
            text = re.sub(r"\s*[|｜]\s*$", "", text)
            text = _WATERMARK.sub("", text).strip()
            if letter in opts or not text:
                continue
            opts[letter] = text
        if len(opts) != 4:
            return []
        # 保持文件内顺序（数据结构为乱序），字母即选项标签，与答案对应
        return [f"{k}. {opts[k]}" for k in opts]

    def _extract_answer(self, block):
        m = re.search(r"\*\*答案\*\*[：:]\s*([A-D])", block)
        if m:
            return m.group(1)
        m = re.search(r"### 答案\s*\n\s*([^\n]*)", block)
        if m:
            m2 = re.search(r"[A-D]", m.group(1))
            if m2:
                return m2.group(0)
        # 组成原理部分题为 "### 答案与解析"，尝试从中提取答案字母
        m = re.search(r"### 答案与解析", block)
        if m:
            seg = block[m.end():m.end() + 400]
            m2 = re.search(r"[A-D](?=。|\s|$)", seg)
            if m2:
                return m2.group(0)
        return None

    def _extract_knowledge_point(self, block):
        m = re.search(r"\*\*考察知识点\*{0,2}\s*[：:]\s*([^\n]+)", block)
        if m:
            return m.group(1).strip().rstrip("*").strip()[:80]
        m = re.search(
            r"### 考察知识点\s*\n(.*?)(?=\n### |\n## |\n\*\*|\Z)", block, re.S
        )
        if m:
            lines = [
                re.sub(r"^[-•]\s*", "", l).strip()
                for l in m.group(1).splitlines()
                if l.strip()
            ]
            lines = [l for l in lines if l and l != "--"]
            return "；".join(lines)[:80]
        return ""


if __name__ == "__main__":
    bank = QuizBank()
    print("\n各科题量:")
    for s in bank.subjects():
        print(f"  {s}: {bank.pool_size(s)}")
