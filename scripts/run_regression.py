"""一键回归：跑 200 题完整评测（默认配置），自动生成对比报告。

用法（项目根目录，408rag 环境）：
    python scripts/run_regression.py

流程：
    1. evaluate.py --adaptive --resume（200 题，断点续跑）
    2. 与基线（eval_results_80_hybrid_oldchunk_complete.json）对比
    3. 生成 results/regression_report.md
"""

import json
import os
import statistics
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable

BENCH = "data/eval_questions_200.json"
BASELINE = "results/eval_results_80_hybrid_oldchunk_complete.json"
OUT_DIR = os.path.join("results", "regression")
REPORT = os.path.join("results", "regression_report.md")


def mean(rows, key):
    vals = [r[key] for r in rows if r.get(key) is not None]
    return round(statistics.mean(vals), 3) if vals else None


def main():
    if not os.path.exists(BENCH):
        print(f"[ERR] 基准文件不存在，先运行 scripts/build_benchmark.py")
        sys.exit(1)

    # 1. 跑评测
    os.makedirs(OUT_DIR, exist_ok=True)
    cmd = [
        "evaluate.py", "--adaptive", "--resume",
        "--questions", BENCH,
        "--output", OUT_DIR,
    ]
    print("[RUN]", " ".join(cmd), flush=True)
    subprocess.run([PY] + cmd, cwd=ROOT, check=True)

    latest = os.path.join(OUT_DIR, "eval_results_latest.json")
    with open(latest, encoding="utf-8") as f:
        cur = json.load(f)
    with open(BASELINE, encoding="utf-8") as f:
        base = json.load(f)

    rows = cur["questions"]
    base_rows = base["questions"]

    # 2. 统计
    subjects = {}
    for r in rows:
        subjects.setdefault(r["subject"], []).append(r)
    lines = []
    lines.append("# KnowMate-408 回归报告")
    lines.append("")
    lines.append(f"- 评测时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- 基准：{BENCH}（{len(rows)} 题）")
    lines.append(f"- 配置：切块 {cur['meta'].get('chunk_size')}/{cur['meta'].get('chunk_overlap')} "
                 f"{cur['meta'].get('chunk_mode')}，rerank={cur['meta'].get('rerank_enabled')}，"
                 f"改写={cur['meta'].get('rewrite_enabled_in_run')}")
    lines.append("")
    lines.append("## 总体指标")
    lines.append("")
    lines.append("| 指标 | 本轮 200 题 | 基线 80 题 |")
    lines.append("|---|---|---|")
    for key, label in [
        ("answer_quality", "回答质量"),
        ("key_point_coverage", "要点命中"),
        ("retrieval_sufficiency", "召回充分性"),
    ]:
        lines.append(f"| {label} | {mean(rows, key)} | {mean(base_rows, key)} |")
    lines.append("")
    lines.append("## 分科（本轮）")
    lines.append("")
    lines.append("| 科目 | 题数 | 回答质量 | 要点命中 | 召回充分性 |")
    lines.append("|---|---|---|---|---|")
    for subj in ["数据结构", "操作系统", "组成原理", "计算机网络"]:
        srows = subjects.get(subj, [])
        lines.append(
            f"| {subj} | {len(srows)} | {mean(srows, 'answer_quality')} | "
            f"{mean(srows, 'key_point_coverage')} | {mean(srows, 'retrieval_sufficiency')} |"
        )
    lines.append("")
    lines.append("## 与基线逐题对比（共同题）")
    lines.append("")
    by_base = {r["id"]: r for r in base_rows}
    common = [r for r in rows if r["id"] in by_base]
    d_aq = []
    d_kp = []
    for r in common:
        b = by_base[r["id"]]
        if r.get("answer_quality") is not None and b.get("answer_quality") is not None:
            d_aq.append(r["answer_quality"] - b["answer_quality"])
        if r.get("key_point_coverage") is not None and b.get("key_point_coverage") is not None:
            d_kp.append(r["key_point_coverage"] - b["key_point_coverage"])
    lines.append(f"- 共同题：{len(common)} 题")
    if d_aq:
        lines.append(f"- 回答质量均值差：{round(statistics.mean(d_aq), 3)}"
                     f"（升 {sum(1 for x in d_aq if x > 0)} / 降 {sum(1 for x in d_aq if x < 0)}）")
    if d_kp:
        lines.append(f"- 要点命中均值差：{round(statistics.mean(d_kp), 3)}"
                     f"（升 {sum(1 for x in d_kp if x > 0)} / 降 {sum(1 for x in d_kp if x < 0)}）")
    lines.append("")
    lines.append(f"完整结果：`{latest}`")
    lines.append("")

    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\n报告已生成: {REPORT}")
    print("\n".join(lines[:18]))


if __name__ == "__main__":
    main()
