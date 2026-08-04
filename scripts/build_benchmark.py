"""把评测基准从 80 题扩展到 200 题。

结构：原 80 道开放问答（data/eval_questions_80.json）
      + 每科新增 30 道（共 120）从清洗题库采样的选择题（带知识点标签）

用法（项目根目录，408rag 环境）：
    python scripts/build_benchmark.py
输出：data/eval_questions_200.json
"""

import json
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from src.quiz_bank import QuizBank


SUBJECT_CODE = {
    "数据结构": "ds",
    "操作系统": "os",
    "组成原理": "co",
    "计算机网络": "net",
}
SAMPLES_PER_SUBJECT = 30
SEED = 408


def main():
    bank = QuizBank()
    with open("data/eval_questions_80.json", encoding="utf-8") as f:
        base = json.load(f)["questions"]
    existing_ids = {q["id"] for q in base}

    random.seed(SEED)
    extra = []
    for subject in SUBJECT_CODE:
        pool = [q for q in bank._pool[subject] if q["answer"]]
        random.shuffle(pool)
        picked = pool[:SAMPLES_PER_SUBJECT]
        for i, q in enumerate(picked, 1):
            qid = f"{SUBJECT_CODE[subject]}-{20 + i}"
            if qid in existing_ids:
                raise RuntimeError(f"id 冲突: {qid}")
            kp = q.get("knowledge_point") or "知识点未标注"
            options_text = "\n".join(q["options"])
            answer_opt = next(
                (o for o in q["options"] if o.startswith(f"{q['answer']}.")), ""
            )
            extra.append({
                "id": qid,
                "subject": subject,
                "kb": f"{subject}_知识点",
                "out_of_kb": False,
                "question": f"{q['question']} 请选出正确选项并说明理由。\n选项：\n{options_text}",
                "answer": f"正确答案：{q['answer']}（{answer_opt}）。知识点：{kp}",
                "key_points": [f"正确答案为 {q['answer']}", kp],
                "knowledge_point": kp,
                "source": q.get("source", ""),
            })

    questions = base + extra
    payload = {
        "meta": {
            "total": len(questions),
            "original_80": len(base),
            "bank_sampled": len(extra),
            "samples_per_subject": SAMPLES_PER_SUBJECT,
            "seed": SEED,
            "source": "data/eval_questions_80.json + 清洗题库采样",
        },
        "questions": questions,
    }
    with open("data/eval_questions_200.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    from collections import Counter
    print("总题数:", len(questions))
    print("各科分布:", dict(Counter(q["subject"] for q in questions)))
    print("带知识点标签:", sum(1 for q in questions if q.get("knowledge_point")))
    print("已写入 data/eval_questions_200.json")


if __name__ == "__main__":
    main()
