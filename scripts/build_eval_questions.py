"""从 data/clean_md/*_题库.md 中抽取评测题集（每科 10 题，共 40 题）。

运行方式（408rag 环境）：
    python scripts/build_eval_questions.py
输出：data/eval_questions.json
"""
import json
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SUBJECTS = ["数据结构", "操作系统", "计算机网络", "组成原理"]
PER_SUBJECT = 10
SRC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "clean_md")
OUT_PATH = os.path.join(os.path.dirname(SRC_DIR), "eval_questions.json")

OPTION_SPLIT = re.compile(r"(?=[A-D][.．、])")


def split_sections(block):
    parts = re.split(r"^###\s*(\S+)", block, flags=re.M)
    d = {}
    for i in range(1, len(parts), 2):
        d[parts[i]] = parts[i + 1].strip()
    return d


def parse_bold_format(block):
    """兼容 `**题目**：` 加粗格式（数据结构题库）。"""

    def grab(label):
        m = re.search(
            rf"\*\*{label}\*\*[：:]\s*(.*?)(?=\n\*\*|\Z)", block, flags=re.S
        )
        return m.group(1).strip() if m else ""

    return {
        "题目": grab("题目"),
        "选项": grab("选项"),
        "答案": grab("答案"),
        "解析": grab("解析"),
    }


def parse_bank(path):
    text = open(path, encoding="utf-8").read()
    blocks = re.split(r"^#{2,3}\s*第\s*\d+\s*题", text, flags=re.M)
    valid = []
    for block in blocks[1:]:
        sec = split_sections(block)
        if not sec.get("题目"):
            sec = parse_bold_format(block)
        q = sec.get("题目", "")
        options = sec.get("选项", "")
        if not options:
            # 兼容「选项内联在题目中」的格式：从题目末尾提取 A-D 选项
            parts = [p.strip() for p in OPTION_SPLIT.split(q) if p.strip()]
            if len(parts) >= 5 and re.match(r"^[A-D][.．、]", parts[-4]):
                options = " | ".join(parts[-4:])
                q = " ".join(parts[:-4])
        ans = sec.get("答案", "")
        if not q or not re.fullmatch(r"[A-D]", ans.strip()):
            continue
        ans_text = ""
        if options:
            parts = [p.strip() for p in re.split(r"[|]", options) if p.strip()]
            if len(parts) == 1:
                parts = [p.strip() for p in OPTION_SPLIT.split(options) if p.strip()]
            for p in parts:
                if p.startswith(ans):
                    ans_text = p[1:].strip(" .．、")
                    break
        valid.append(
            {
                "question": q.strip(),
                "options": options,
                "answer": ans.strip(),
                "answer_text": ans_text,
                "reference": f"答案：{ans.strip()}\n解析：{sec.get('解析', '')}".strip(),
            }
        )
    return valid


def sample_even(items, n):
    if len(items) <= n:
        return items
    idxs = {round(i * (len(items) - 1) / (n - 1)) for i in range(n)}
    return [items[i] for i in sorted(idxs)]


def main():
    out = []
    for subject in SUBJECTS:
        path = os.path.join(SRC_DIR, f"{subject}_题库.md")
        items = parse_bank(path)
        if len(items) < PER_SUBJECT:
            print(f"[WARN] {subject}: 仅解析到 {len(items)} 题")
        chosen = sample_even(items, PER_SUBJECT)
        print(f"{subject}: 解析 {len(items)} 题，抽样 {len(chosen)} 题")
        for i, item in enumerate(chosen, 1):
            out.append(
                {
                    "id": f"{subject[:2].upper()}-{i:02d}",
                    "subject": subject,
                    "kb": f"{subject}_知识点",
                    **item,
                }
            )
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump({"count": len(out), "questions": out}, f, ensure_ascii=False, indent=2)
    print(f"\n共 {len(out)} 题 → {OUT_PATH}")


if __name__ == "__main__":
    main()
