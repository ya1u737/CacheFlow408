"""批量判定操作系统题库缺失答案的选择题，并把答案直接写回 题库 md。

目的：操作系统题库绝大多数题没有答案，导致出题时需要实时调用本地 LLM 判题（慢）。
本脚本一次性用本地模型（带知识点检索 grounding）判完全部缺答案题，写入：

    ### 答案

    X

之后操作系统出题即为纯题库直出，无需再走 LLM。

用法（项目根目录，408rag 环境）：
    python scripts/batch_judge_os.py --dry-run     # 只判题不写文件
    python scripts/batch_judge_os.py --limit 5     # 只处理前 5 道（冒烟）
    python scripts/batch_judge_os.py               # 完整批量

判题结果同时写入 storage/quiz_os_answers.json 缓存（逐题落盘），中断后重跑可续。
"""

import argparse
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from src.config import Config
from src.quiz_bank import QuizBank, SUBJECT_FILES, _HEADER_RE
from src.generator import AnswerGenerator
from backend.quiz_service import QuizService


def main():
    parser = argparse.ArgumentParser(description="批量判定操作系统题库答案并写回 md")
    parser.add_argument("--dry-run", action="store_true", help="只判题，不写入 md")
    parser.add_argument("--limit", type=int, default=None, help="最多处理 N 道（冒烟测试）")
    args = parser.parse_args()

    os_path = os.path.join(Config.QUIZ_BANK_DIR, SUBJECT_FILES["操作系统"])
    text = open(os_path, encoding="utf-8").read()

    # 判题阶段保持 embedding 模型常驻，避免每题重新加载（复用重建脚本的做法）
    Config.EMBEDDING_KEEP_ALIVE = 1800
    bank = QuizBank()
    svc = QuizService(AnswerGenerator())

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

    matches = list(_HEADER_RE.finditer(text))
    insertions = []
    judged = 0
    failed = 0
    consecutive_fail = 0

    for idx, m in enumerate(matches):
        number = int(m.group(1))
        start = m.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        block = text[start:end]
        if "### 答案" in block:
            continue  # 已有答案，跳过
        q = bank._parse_block("操作系统", number, block)
        if q is None:
            continue

        ans = q["answer"]
        if ans is None:
            try:
                ans = svc._judge_answer(q)  # 内部带缓存 + grounding + 重试
            except Exception as e:
                failed += 1
                consecutive_fail += 1
                print(f"[FAIL] {q['id']}: {type(e).__name__}: {e}", flush=True)
                if consecutive_fail >= 5:
                    print("[ABORT] 连续失败过多，请检查 Ollama 后重跑（缓存已保留）", flush=True)
                    break
                continue
            consecutive_fail = 0
            judged += 1
            print(f"[OK] {q['id']}: 答案 {ans}", flush=True)

        kp = block.find("### 考察知识点")
        pos = start + (kp if kp >= 0 else len(block))
        insertions.append((pos, f"### 答案\n\n{ans}\n\n"))

        if args.limit and judged >= args.limit:
            break

    print(f"\n完成：判定 {judged} 道，失败 {failed} 道，待写入 {len(insertions)} 道答案", flush=True)
    if args.dry_run:
        print("[dry-run] 未写入文件", flush=True)
        return
    if insertions:
        for pos, ins in sorted(insertions, reverse=True):
            text = text[:pos] + ins + text[pos:]
        with open(os_path, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"已写入 {len(insertions)} 道答案 -> {os_path}", flush=True)


if __name__ == "__main__":
    main()
