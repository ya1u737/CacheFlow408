"""对比多轮评测结果（完整 payload 或 partial 均可）。

用法:
    python scripts/compare_eval.py results/eval_results_80_adaptive_complete.json \
        results/leg1_hybrid_oldchunk/eval_results_latest.json

输出:
    - 每轮整体 + 分科均值（回答质量 / 要点命中 / 召回充分性）
    - 两两对比：共同题目上的提升/退步统计
"""
import json
import statistics
import sys


def load_rows(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    return data.get("questions") or data.get("results") or []


def mean(rows, key):
    vals = [r[key] for r in rows if r.get(key) is not None]
    return round(statistics.mean(vals), 3) if vals else None


def summarize(rows):
    subjects = {}
    for r in rows:
        subjects.setdefault(r["subject"], []).append(r)
    out = {}
    for subj, srows in subjects.items():
        out[subj] = {
            "n": len(srows),
            "answer_quality": mean(srows, "answer_quality"),
            "key_point_coverage": mean(srows, "key_point_coverage"),
            "retrieval_sufficiency": mean(srows, "retrieval_sufficiency"),
        }
    out["__all__"] = {
        "n": len(rows),
        "answer_quality": mean(rows, "answer_quality"),
        "key_point_coverage": mean(rows, "key_point_coverage"),
        "retrieval_sufficiency": mean(rows, "retrieval_sufficiency"),
    }
    return out


def diff(a, b, rows_a, rows_b):
    """b 相对 a 的逐题差异统计（共同题目）。"""
    by_a = {r["id"]: r for r in rows_a}
    by_b = {r["id"]: r for r in rows_b}
    common = sorted(set(by_a) & set(by_b))
    if not common:
        return None
    d_aq = []
    d_kp = []
    for qid in common:
        ra, rb = by_a[qid], by_b[qid]
        if ra.get("answer_quality") is not None and rb.get("answer_quality") is not None:
            d_aq.append(round(rb["answer_quality"] - ra["answer_quality"], 2))
        if (
            ra.get("key_point_coverage") is not None
            and rb.get("key_point_coverage") is not None
        ):
            d_kp.append(round(rb["key_point_coverage"] - ra["key_point_coverage"], 3))
    return {
        "common_n": len(common),
        "aq_mean_delta": round(statistics.mean(d_aq), 3) if d_aq else None,
        "aq_improved": sum(1 for x in d_aq if x > 0),
        "aq_worsened": sum(1 for x in d_aq if x < 0),
        "kp_mean_delta": round(statistics.mean(d_kp), 3) if d_kp else None,
        "kp_improved": sum(1 for x in d_kp if x > 0),
        "kp_worsened": sum(1 for x in d_kp if x < 0),
    }


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    runs = []
    for path in sys.argv[1:]:
        rows = load_rows(path)
        runs.append((path, rows, summarize(rows)))

    labels = [path.split("/")[-1] for path, _, _ in runs]
    print(f"{'科目':<10}", *[f"{lbl[:18]:>22}" for lbl in labels])
    for key, label in [
        ("answer_quality", "回答质量"),
        ("key_point_coverage", "要点命中"),
        ("retrieval_sufficiency", "召回充分性"),
    ]:
        print(label)
        for subj in runs[0][2]:
            print(
                f"  {subj:<12}",
                *[f"{str(run[2].get(subj, {}).get(key)):>22}" for run in runs],
            )

    if len(runs) >= 2:
        print("\n两两对比（后一轮相对前一轮，共同题目）:")
        for i in range(len(runs) - 1):
            d = diff(runs[i][1], runs[i + 1][1], runs[i][1], runs[i + 1][1])
            if d is None:
                continue
            print(
                f"  {labels[i+1]} vs {labels[i]}: "
                f"共同 {d['common_n']} 题 | 回答质量均值 Δ{d['aq_mean_delta']} "
                f"(升 {d['aq_improved']}/降 {d['aq_worsened']}) | "
                f"要点命中均值 Δ{d['kp_mean_delta']} (升 {d['kp_improved']}/降 {d['kp_worsened']})"
            )


if __name__ == "__main__":
    main()
