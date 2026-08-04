"""把评测结果导出为 Markdown（.md.txt）文档。

用法:
    python scripts/export_eval_markdown.py "D:/desktop/408RAG评测结果"
"""
import json
import os
import statistics
import sys


RESULT_FILES = {
    "baseline": "results/eval_results_80_baseline_complete.json",
    "adaptive": "results/eval_results_80_adaptive_complete.json",
    "hybrid_oldchunk": "results/eval_results_80_hybrid_oldchunk_complete.json",
    "hybrid_semantic": "results/eval_results_80_hybrid_semantic_complete.json",
}

RUN_NAMES = {
    "baseline": "纯模型基线",
    "adaptive": "纯向量检索（固定切块）",
    "hybrid_oldchunk": "混合检索（固定切块）",
    "hybrid_semantic": "混合检索（语义切块）",
}

SUBJECTS = ["数据结构", "操作系统", "计算机网络", "组成原理"]


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def mean(rows, key):
    vals = [r[key] for r in rows if r.get(key) is not None]
    return round(statistics.mean(vals), 3) if vals else None


def fmt(v, digits=2):
    return "—" if v is None else f"{v:.{digits}f}"


def per_subject(data, key):
    out = {}
    for subj in SUBJECTS:
        rows = [r for r in data["questions"] if r.get("subject") == subj]
        out[subj] = mean(rows, key)
    return out


def gate_dist(rows):
    g = sum(1 for r in rows if r.get("mode_used") == "grounded")
    f = sum(1 for r in rows if r.get("mode_used") == "fallback")
    return g, f


def question_table(rows, show_mode=True):
    lines = [
        "| ID | 科目 | 题目 | 模式 | 重排最高分 | 召回充分性 | 回答质量 | 要点命中率 | 生成耗时(s) |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in sorted(rows, key=lambda x: x["id"]):
        q = r["question"]
        q = q[:60] + ("…" if len(q) > 60 else "")
        mode = r.get("mode_used") or "—"
        lines.append(
            f"| {r['id']} | {r['subject']} | {q} | {mode} | "
            f"{fmt(r.get('rerank_top_score'))} | {fmt(r.get('retrieval_sufficiency'))} | "
            f"{fmt(r.get('answer_quality'))} | {fmt(r.get('key_point_coverage'))} | "
            f"{fmt(r.get('generation'), 1)} |"
        )
    return "\n".join(lines)


def overall_table(datasets):
    lines = [
        "| 轮次 | 回答质量 | 要点命中 | 召回充分性 | grounded | fallback | 平均 total(s) | 平均检索(s) | 平均生成(s) | p95 total(s) |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for key in ["baseline", "adaptive", "hybrid_oldchunk", "hybrid_semantic"]:
        d = datasets[key]
        rows = d["questions"]
        s = d["summary"].get("__overall__", {})
        p95 = d["summary"].get("__p95__", {})
        g, f = gate_dist(rows)
        lines.append(
            f"| {RUN_NAMES[key]} | {fmt(s.get('answer_quality'))} | "
            f"{fmt(s.get('key_point_coverage'))} | {fmt(s.get('retrieval_sufficiency'))} | "
            f"{g} | {f} | {fmt(s.get('total'), 1)} | {fmt(s.get('retrieval'), 1)} | "
            f"{fmt(s.get('generation'), 1)} | {fmt(p95.get('total'), 1)} |"
        )
    return "\n".join(lines)


def subject_table(datasets, key, label):
    lines = [f"### {label}", "", "| 科目 | 纯模型 | 纯向量 | 混合+固定 | 混合+语义 |", "| --- | --- | --- | --- | --- |"]
    for subj in SUBJECTS:
        vals = [per_subject(datasets[k], key).get(subj) for k in
                ["baseline", "adaptive", "hybrid_oldchunk", "hybrid_semantic"]]
        lines.append(f"| {subj} | {' | '.join(fmt(v) for v in vals)} |")
    return "\n".join(lines)


def pairwise_stats(a, b):
    ma = {r["id"]: r for r in a}
    mb = {r["id"]: r for r in b}
    common = sorted(set(ma) & set(mb))
    d_aq = []
    d_kp = []
    for qid in common:
        ra, rb = ma[qid], mb[qid]
        if ra.get("answer_quality") is not None and rb.get("answer_quality") is not None:
            d_aq.append(rb["answer_quality"] - ra["answer_quality"])
        if (ra.get("key_point_coverage") is not None
                and rb.get("key_point_coverage") is not None):
            d_kp.append(rb["key_point_coverage"] - ra["key_point_coverage"])
    return {
        "n": len(common),
        "aq_delta": round(statistics.mean(d_aq), 3) if d_aq else None,
        "aq_up": sum(1 for x in d_aq if x > 0),
        "aq_down": sum(1 for x in d_aq if x < 0),
        "kp_delta": round(statistics.mean(d_kp), 3) if d_kp else None,
        "kp_up": sum(1 for x in d_kp if x > 0),
        "kp_down": sum(1 for x in d_kp if x < 0),
    }


def build_all(datasets):
    files = {}
    today = "2026-08-03"

    # ---- 00 总览 ----
    ov = datasets["hybrid_semantic"]
    content = f"""# 408 学习助手 · RAG 评测总览

> 生成日期：{today} ｜ 评测题量：80 题（数据结构 / 操作系统 / 计算机网络 / 组成原理 各 20 题） ｜ 裁判：qwen2.5:7b（本地）

## 一句话结论

混合检索（向量 + BM25 + RRF）带来显著提升；语义切块本轮未胜出，不作为默认配置。

## 整体指标对比

{overall_table(datasets)}

## 核心结论

1. **混合检索是主线收益**：回答质量 3.79 → 3.99，要点命中 0.735 → 0.821，召回充分性 4.25 → 4.66，四科全面领先，且无需重建向量库。
2. **语义切块（标题/段落组织）未加分**：回答质量持平，要点命中反而从 0.821 降至 0.797（13 升 / 19 降），主要原因是块变碎、top-3 上下文覆盖变差。产品默认建议采用「混合检索 + 固定切块」。
3. **reranker 尚未做开关 A/B**：全链路唯一未评测环节，门控信号依赖其分数，需加 `--no-rerank` 公平开关后补测。
4. **端到端延迟**：平均约 8-8.5s/问（本地 7B 生成为主），p95 约 13-14s。

## 文件清单

1. `01_整体与分科对比.md.txt`：三轮整体 + 分科 + 逐题升降统计
2. `02_逐题明细_纯模型基线.md.txt`
3. `03_逐题明细_纯向量检索.md.txt`
4. `04_逐题明细_混合检索_固定切块.md.txt`
5. `05_逐题明细_混合检索_语义切块.md.txt`
6. `06_评测配置与口径.md.txt`
"""
    files["00_总览与结论.md.txt"] = content

    # ---- 01 整体与分科对比 ----
    s12 = pairwise_stats(datasets["adaptive"]["questions"],
                         datasets["hybrid_oldchunk"]["questions"])
    s23 = pairwise_stats(datasets["hybrid_oldchunk"]["questions"],
                         datasets["hybrid_semantic"]["questions"])
    content = f"""# 整体与分科对比

## 整体指标

{overall_table(datasets)}

## 分科对比

{subject_table(datasets, "answer_quality", "回答质量（1-5 分）")}

{subject_table(datasets, "key_point_coverage", "要点命中率（0-1 比例）")}

{subject_table(datasets, "retrieval_sufficiency", "召回充分性（1-5 分）")}

## 逐题升降统计（共同 80 题）

### 混合检索 vs 纯向量

- 回答质量：均值 Δ+{s12['aq_delta']}（{s12['aq_up']} 题升 / {s12['aq_down']} 题降）
- 要点命中：均值 Δ+{s12['kp_delta']}（{s12['kp_up']} 题升 / {s12['kp_down']} 题降）

### 语义切块 vs 固定切块（同为混合检索）

- 回答质量：均值 Δ{s23['aq_delta']}（{s23['aq_up']} 题升 / {s23['aq_down']} 题降）
- 要点命中：均值 Δ{s23['kp_delta']}（{s23['kp_up']} 题升 / {s23['kp_down']} 题降）

## 门控（分级降级）分布

| 轮次 | grounded（接地回答） | fallback（纯模型） |
| --- | --- | --- |
"""
    for key in ["adaptive", "hybrid_oldchunk", "hybrid_semantic"]:
        g, f = gate_dist(datasets[key]["questions"])
        content += f"| {RUN_NAMES[key]} | {g} | {f} |\n"
    files["01_整体与分科对比.md.txt"] = content

    # ---- 逐题明细 ----
    per_question = [
        ("02_逐题明细_纯模型基线.md.txt", "baseline"),
        ("03_逐题明细_纯向量检索.md.txt", "adaptive"),
        ("04_逐题明细_混合检索_固定切块.md.txt", "hybrid_oldchunk"),
        ("05_逐题明细_混合检索_语义切块.md.txt", "hybrid_semantic"),
    ]
    for fname, key in per_question:
        d = datasets[key]
        rows = d["questions"]
        content = f"# 逐题明细 · {RUN_NAMES[key]}\n\n> 共 {len(rows)} 题；要点命中率为生成答案对标准答案要点的覆盖比例。\n\n"
        content += question_table(rows) + "\n"
        files[fname] = content

    # ---- 06 配置与口径 ----
    m = datasets["hybrid_semantic"]["meta"]
    content = f"""# 评测配置与口径

## 评测口径

- 题量：80 题（四科各 20 题），含标准答案与 key_points
- 指标：
  - 回答质量 answer_quality（1-5，宽口径，对照标准答案）
  - 要点命中率 key_point_coverage（生成答案覆盖的标准答案要点比例）
  - 召回充分性 retrieval_sufficiency（1-5，检索资料是否足以回答问题，纯模型轮不适用）
- 裁判：qwen2.5:7b（本地 Ollama），单次调用同时输出三个指标
- 模式：adaptive（门控：reranker 最高分 < 0.5 时降级为纯模型回答）

## 链路与模型

- 查询改写：qwen2.5:1.5b（keep_alive=0）
- 向量检索：bge-m3（Chroma）
- 词法检索：BM25（中文字 + 双字二元组）
- 融合：RRF（k=60，dense/BM25 各取 top-10，融合后取 top-5）
- 重排：bge-reranker-v2-m3（fp16，取 top-3）
- 生成：qwen2.5:7b（num_ctx=8192）
- 门控阈值：RAG_FALLBACK_THRESHOLD = 0.5

## 切块配置

- 固定切块（recursive）：chunk_size=800 / overlap=150
- 语义切块（semantic）：按标题章节组织，超长章节按段落/句子切分，标题作为块上下文前缀

## 结果文件

{chr(10).join(f'- {os.path.basename(p)}' for p in RESULT_FILES.values())}
"""
    files["06_评测配置与口径.md.txt"] = content
    return files


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "D:/desktop/408RAG评测结果"
    os.makedirs(out_dir, exist_ok=True)
    datasets = {k: load(v) for k, v in RESULT_FILES.items()}
    files = build_all(datasets)
    for name, content in files.items():
        path = os.path.join(out_dir, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print("written:", path, f"({len(content)} chars)")
    print("done, total files:", len(files))


if __name__ == "__main__":
    main()
