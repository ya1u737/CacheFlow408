# KnowMate-408 RAG 评测报告

## 评测体系

- 题库：`data/eval_questions_80.json`，80 题（数据结构 / 操作系统 / 组成原理 / 计算机网络 各 20 题，其中 3 道为知识库外超纲题）
- 裁判：本地 `qwen2.5:7b`（temperature=0），一次调用同时给出召回充分性、回答质量、要点命中率
- 链路：查询改写（qwen2.5:1.5b）→ 混合检索（bge-m3 + BM25 + RRF）→ rerank（bge-reranker-v2-m3 fp16）→ 门控 → 生成（qwen2.5:7b）
- 指标：answer_quality（1-5）、key_point_coverage（要点命中率）、retrieval_sufficiency（1-5）

## 轮次总览

| 轮次 | 配置 | 回答质量 | 要点命中 | 召回充分性 |
|---|---|---|---|---|
| baseline | 纯模型，不检索 | 3.55 | 0.670 | — |
| adaptive | 纯向量 + 门控（固定切块） | 3.79 | 0.735 | 4.25 |
| leg1（默认） | 混合检索 + 固定切块 800/150 + rerank + 门控 | 3.99 | 0.821 | 4.66 |
| leg2 | 混合检索 + 语义切块 | 3.99 | 0.797 | 4.67 |
| leg3 | 混合检索 + 固定切块，关闭 rerank/门控 | 3.88 | 0.784 | 4.45 |
| chunk400 | 混合检索，切块 400/150 | 3.96 | 0.781 | 4.39 |
| chunk1200 | 混合检索，切块 1200/150 | 3.93 | 0.768 | 4.45 |

## 关键结论

1. **混合检索全面优于纯向量**：回答质量 3.79→3.99、要点命中 0.735→0.821、召回充分性 4.25→4.66，四科全胜。
2. **语义切块未胜出**：质量持平，要点命中 0.797 < 0.821，不作为默认；产品默认固定切块 + 混合检索（leg1 配置）。
3. **reranker + 门控保留**：关闭后 80 题回答质量 3.99→3.88、要点命中 0.821→0.784、召回 4.66→4.45；差距主要来自超库题门控（关闭后 3 道超库题全部被迫 grounded，1 分）。单题检索延迟从 2.7s 降至 0.5s，但质量损失不划算。
4. **chunk 尺寸 800/150 最优**：400（3.96/0.781/4.39）与 1200（3.93/0.768/4.45）均未超越基线，保持默认。
5. **门控误报案例（os-20 “活锁”）**：reranker 高分 0.687 但内容无关，门控未触发；生成端“上下文不足拒绝”规则兜底，未产生幻觉但要点得分为 1。结论：阈值调优无法干净解决，后续可引入引用溯源/faithfulness 二次校验。
6. **操作系统题库已补齐答案**：426 道由本地模型（带知识点 grounding）判定并写回 md，出题改为纯题库直出（秒出），不再实时调用 LLM。

## 结果文件索引

- 纯模型基线：`results/eval_results_80_baseline_complete.json`
- 纯向量：`results/eval_results_80_adaptive_complete.json`
- 混合检索 + 固定切块（默认 leg1）：`results/eval_results_80_hybrid_oldchunk_complete.json`
- 混合检索 + 语义切块：`results/eval_results_80_hybrid_semantic_complete.json`
- 关闭 rerank：`results/eval_results_80_norerank_recursive_complete.json`
- chunk 400：`results/eval_results_80_chunk400_complete.json`
- chunk 1200：`results/eval_results_80_chunk1200_complete.json`

各轮详细日志与增量结果位于 `results/leg_*/`，可用 `scripts/compare_eval.py` 两两对比，用 `scripts/export_eval_markdown.py` 导出 Markdown。

## 复现方式

```bash
# 重建指定切块参数的向量库（可指定库根目录，避免覆盖默认库）
python scripts/rebuild_kb.py --chunk-size 400 --overlap 150 --kb-root storage/chroma_s400

# 跑完整评测（rerank + 门控，断点续跑）
python evaluate.py --adaptive --resume --questions data/eval_questions_80.json \
  --kb-root storage/chroma_s400 --output results/leg_chunk400

# 一键跑切块矩阵
python scripts/chunk_eval_runner.py

# 对比多轮结果
python scripts/compare_eval.py results/eval_results_80_hybrid_oldchunk_complete.json \
  results/eval_results_80_chunk400_complete.json results/eval_results_80_chunk1200_complete.json
```
