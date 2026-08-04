"""408 RAG 离线评测脚本。

用法（408rag 环境）：
    python evaluate.py                     # 完整链路：检索 + 生成 + LLM 打分（40 题）
    python evaluate.py --retrieval-only    # 快速模式：只检索 + 召回充分性打分
    python evaluate.py --limit 3           # 只跑前 N 题（冒烟测试）
    python evaluate.py --resume            # 断点续跑（跳过已完成的题）

设计约定：
- 改写与向量化在评测开始时预跑一遍（8GB 显存下避免小模型与 7b 反复换入换出），
  每题改写/向量化耗时单独记录到 query_process / embedding 阶段；
- 主循环：检索（vector_search + GPU rerank）+ 生成 + LLM 打分；
- 打分：每题一次 LLM 调用，同时输出两个 1-5 分
    retrieval_sufficiency  检索到的 TOP-K 资料是否充分覆盖回答该问题所需信息
    answer_quality         对照参考答案，生成回答是否正确、完整
- 裁判默认本地 qwen2.5:7b（免费）；--judge-backend api 可切换 DeepSeek 等云端（需 DEEPSEEK_API_KEY）；
- 每题完成后增量保存 results/eval_results_partial.json，中途崩溃可 --resume 续跑。
"""
import argparse
import json
import os
import re
import statistics
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from src.config import Config
from src.generator import AnswerGenerator
from src.performance import RAGTimer
from src.query_processor import QueryProcessor
from src.retriever import KnowledgeBase

JUDGE_PROMPT = """你是408考研评测裁判。请对一次RAG问答按宽口径标准打分，只输出一个 JSON 对象。

评分标准（相对宽松，不苛求措辞与参考答案一致，核心意思正确即可）：
- answer_quality: 5=结论正确且关键点齐全；4=结论正确、关键点基本覆盖；3=结论正确但漏了部分关键点；2=结论部分正确；1=结论错误
- retrieval_sufficiency: 1-5，检索到的资料是否提供了回答该问题所需的关键概念与依据（1=完全缺失或无关，3=部分覆盖，5=充分覆盖；不要求资料直接给出完整答案）
- key_points_covered: 整数，生成的回答覆盖了几个【参考答案关键点】
- key_points_total: 整数，参考答案关键点总数
- retrieval_reason: 一句话中文理由
- answer_reason: 一句话中文理由

【用户问题】
{question}

【检索到的资料（TOP-{top_k}）】
{contexts}

【参考答案】
{reference}

【参考答案关键点】
{key_points}

【生成的回答】
{answer}

只输出 JSON："""

BASELINE_PROMPT = """你是考研408辅导助手（数据结构、操作系统、计算机网络、计算机组成原理）。
请直接回答下面的问题，不依赖任何外部资料：
1. 先给出结论；
2. 再给出理由或解析；
3. 如果是选择题，说明正确选项及原因，并简要解释错误选项。

问题：{question}

回答："""


class Judge:
    """LLM 打分器：一次调用同时输出召回充分性 + 回答质量。"""

    def __init__(self, backend=None, model=None):
        self.backend = backend or Config.EVAL_JUDGE_BACKEND
        self.model = model or Config.EVAL_JUDGE_MODEL
        if self.backend == "api":
            key = os.getenv("DEEPSEEK_API_KEY", "").strip()
            if not key:
                raise RuntimeError("EVAL_JUDGE_BACKEND=api 但未配置 DEEPSEEK_API_KEY")
            self.llm = ChatOpenAI(
                model=self.model, api_key=key, base_url=Config.API_BASE, temperature=0
            )
            print(f"[JUDGE] 云端裁判: {self.model}")
        else:
            self.llm = ChatOllama(model=self.model, temperature=0, num_ctx=8192)
            print(f"[JUDGE] 本地裁判: {self.model}")

    def score(self, question, contexts, reference, answer, top_k, key_points=None):
        prompt = JUDGE_PROMPT.format(
            question=question,
            contexts=contexts,
            reference=reference,
            answer=answer or "（本模式未生成回答，仅评估检索充分性）",
            top_k=top_k,
            key_points="\n".join(f"- {p}" for p in (key_points or [])) or "（无）",
        )
        t0 = time.time()
        try:
            resp = self.llm.invoke(prompt)
            text = resp.content if hasattr(resp, "content") else str(resp)
        except Exception as e:
            print(f"[JUDGE] 打分失败: {e}")
            return {
                "retrieval_sufficiency": None,
                "answer_quality": None,
                "key_points_covered": None,
                "key_points_total": None,
                "retrieval_reason": f"error: {e}",
                "answer_reason": "",
                "judge_time": round(time.time() - t0, 3),
            }
        data = _parse_scores(text)
        data["judge_time"] = round(time.time() - t0, 3)
        return data


def _parse_scores(text):
    scores = {
        "retrieval_sufficiency": None,
        "answer_quality": None,
        "key_points_covered": None,
        "key_points_total": None,
        "retrieval_reason": "",
        "answer_reason": "",
    }
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        try:
            obj = json.loads(m.group(0))
            for k in scores:
                if k in obj:
                    scores[k] = obj[k]
            return scores
        except json.JSONDecodeError:
            pass
    rs = re.search(r"retrieval_sufficiency[\"']?\s*[:：]\s*(\d)", text)
    aq = re.search(r"answer_quality[\"']?\s*[:：]\s*(\d)", text)
    kc = re.search(r"key_points_covered[\"']?\s*[:：]\s*(\d+)", text)
    kt = re.search(r"key_points_total[\"']?\s*[:：]\s*(\d+)", text)
    if rs:
        scores["retrieval_sufficiency"] = int(rs.group(1))
    if aq:
        scores["answer_quality"] = int(aq.group(1))
    if kc:
        scores["key_points_covered"] = int(kc.group(1))
    if kt:
        scores["key_points_total"] = int(kt.group(1))
    return scores


def load_questions(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)["questions"]


def build_contexts(docs):
    parts = []
    for i, doc in enumerate(docs, 1):
        src = doc.metadata.get("source", "?")
        page = doc.metadata.get("page", "?")
        parts.append(f"[资料{i}] 来源:{src} 第{page}页\n{doc.page_content}")
    return "\n\n".join(parts)


def _mean(rows, key):
    vals = [r[key] for r in rows if r.get(key) is not None]
    return round(statistics.mean(vals), 2) if vals else None


def _error_record(q, rewritten, err):
    return {
        "id": q["id"],
        "subject": q["subject"],
        "question": q["question"],
        "rewritten": rewritten,
        "answer": None,
        "retrieval_sufficiency": None,
        "answer_quality": None,
        "key_point_coverage": None,
        "total": 0.0,
        "retrieval": 0.0,
        "generation": 0.0,
        "error": err,
        "scores": {
            "retrieval_sufficiency": None,
            "answer_quality": None,
            "retrieval_reason": "",
            "answer_reason": "",
        },
        "latency": {},
        "judge_time": 0.0,
        "references": [],
    }


def run_eval(args):
    questions = load_questions(args.questions)
    if args.ids:
        wanted = {s.strip() for s in args.ids.split(",") if s.strip()}
        questions = [q for q in questions if q["id"] in wanted]
    if args.limit:
        questions = questions[: args.limit]

    kb = None if args.baseline else KnowledgeBase(rerank_enabled=not args.no_rerank)
    qproc = (
        None
        if args.baseline or args.no_rewrite
        else QueryProcessor() if Config.QUERY_REWRITE_ENABLED else None
    )
    if args.no_rerank:
        print("[EVAL] --no-rerank: 跳过 Cross Encoder，按融合分取 top-3，门控关闭（A/B 对照）")
    gen = AnswerGenerator()
    if not gen.switch_mode(args.gen_backend):
        raise RuntimeError(
            f"生成后端 {args.gen_backend} 不可用：api 模式需先配置 DEEPSEEK_API_KEY"
        )
    judge = Judge(args.judge_backend, args.judge_model)
    retrieval_only = args.retrieval_only

    # 断点续跑
    partial_path = os.path.join(args.output, "eval_results_partial.json")
    done_ids = set()
    results = []
    if args.resume and os.path.exists(partial_path):
        with open(partial_path, encoding="utf-8") as f:
            results = json.load(f)
        done_ids = {r["id"] for r in results}
        print(
            f"[EVAL] 续跑模式：保留已保存 {len(results)} 条结果，"
            f"跳过已完成 {len(done_ids)} 题"
        )

    def save_partial():
        os.makedirs(args.output, exist_ok=True)
        with open(partial_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

    t_start = time.time()
    skipped = 0

    # 预改写：一次性完成全部改写，耗时逐题记录到 query_process
    rewrites = {}
    if qproc is not None:
        print(f"[EVAL] 预改写 {len(questions)} 题 ...")
        for q in questions:
            t0 = time.time()
            rewritten = qproc.rewrite(q["question"])  # 内部已做超时/异常回退
            rewrites[q["id"]] = (rewritten, round(time.time() - t0, 3))

    # 预向量化：一次性完成全部查询向量化，耗时逐题记录到 embedding
    embeds = {}
    if kb is not None:
        print(f"[EVAL] 预向量化 {len(questions)} 题 ...")
    for q in ([] if kb is None else questions):
        rw, _ = rewrites.get(q["id"], (q["question"], 0.0))
        vec, ok = None, False
        t0 = time.time()
        for attempt in range(3):
            try:
                vec = kb.embedding.embed_query(rw)
                ok = True
                break
            except Exception as e:
                print(
                    f"[EVAL] {q['id']} 向量化失败(第{attempt + 1}/3): "
                    f"{type(e).__name__}: {e}"
                )
                time.sleep(6)
        embeds[q["id"]] = (vec if ok else None, round(time.time() - t0, 3))

    loaded_kb = None
    for idx, q in enumerate(questions, 1):
        if q["id"] in done_ids:
            continue

        timer = RAGTimer()
        if qproc is not None:
            rewritten, rw_time = rewrites.get(q["id"], (q["question"], 0.0))
        else:
            rewritten, rw_time = q["question"], 0.0

        if kb is not None:
            # 切换知识库
            kb_name = q.get("kb")
            if kb_name and kb_name != loaded_kb:
                try:
                    ok_load = kb.load_persistent(kb_name)
                except Exception as e:
                    ok_load = False
                    print(f"[EVAL] {q['id']} 加载向量库失败: {type(e).__name__}: {e}")
                if not ok_load:
                    print(f"[EVAL] 警告: 向量库 {kb_name} 不存在或加载失败，跳过该题")
                    skipped += 1
                    continue
                loaded_kb = kb_name

            vec, embed_time = embeds.get(q["id"], (None, 0.0))
            try:
                docs = kb.search(rewritten, timer=timer, query_embedding=vec)
            except Exception as e:
                print(f"[EVAL] {q['id']} 检索失败: {type(e).__name__}: {e}")
                results.append(_error_record(q, rewritten, f"retrieval: {e}"))
                save_partial()
                continue
            rerank_top_score = getattr(kb, "last_rerank_top_score", None)
            contexts = build_contexts(docs)
        else:
            vec, embed_time = None, 0.0
            docs = []
            rerank_top_score = None
            contexts = "（纯模型基线：未检索知识库）"

        timer.start("query_process")
        timer.end("query_process")

        # 分级降级：检索置信度不足时用纯模型回答（--adaptive 模式验证真实门控）
        mode_used = "grounded"
        if (
            kb is not None
            and args.adaptive
            and not retrieval_only
            and not args.no_rerank
        ):
            if (
                rerank_top_score is None
                or rerank_top_score < Config.RAG_FALLBACK_THRESHOLD
            ):
                mode_used = "fallback"

        answer, gen_err = None, None
        if not retrieval_only:
            try:
                if args.baseline or (args.adaptive and mode_used == "fallback"):
                    llm = gen.get_llm()
                    prompt = BASELINE_PROMPT.format(question=q["question"])
                    stream = timer.timed_iterable("llm_generation", llm.stream(prompt))
                else:
                    stream = gen.generate(q["question"], docs, [], timer=timer)
                answer = "".join(
                    ch.content if hasattr(ch, "content") else str(ch)
                    for ch in stream
                )
            except Exception as e:
                gen_err = f"{type(e).__name__}: {e}"
                print(f"[EVAL] {q['id']} 生成失败: {gen_err}")

        timer.end("total")
        perf = timer.to_dict()
        # 改写/向量化耗时在预跑阶段测得，回填对应阶段
        perf["query_process"] = rw_time
        perf["embedding"] = embed_time

        reference = q.get("reference") or q.get("answer", "")
        jr = judge.score(
            q["question"], contexts, reference, answer, len(docs), q.get("key_points")
        )
        if retrieval_only:
            jr["answer_quality"] = None
        if args.baseline:
            jr["retrieval_sufficiency"] = None
        if jr["key_points_total"] and jr["key_points_covered"] is not None:
            kp_coverage = round(jr["key_points_covered"] / jr["key_points_total"], 3)
        else:
            kp_coverage = None

        rec = {
            "id": q["id"],
            "subject": q["subject"],
            "knowledge_point": q.get("knowledge_point", ""),
            "question": q["question"],
            "rewritten": rewritten,
            "answer": answer,
            "mode_used": mode_used if args.adaptive else None,
            "rerank_top_score": rerank_top_score,
            "retrieval_sufficiency": jr["retrieval_sufficiency"],
            "answer_quality": jr["answer_quality"],
            "key_point_coverage": kp_coverage,
            "total": perf["total"],
            "retrieval": round(
                perf["embedding"] + perf["vector_search"] + perf["rerank"], 3
            ),
            "generation": perf["llm_generation"],
            "error": gen_err,
            "scores": {
                "retrieval_sufficiency": jr["retrieval_sufficiency"],
                "answer_quality": jr["answer_quality"],
                "retrieval_reason": jr["retrieval_reason"],
                "answer_reason": jr["answer_reason"],
            },
            "latency": perf,
            "judge_time": jr["judge_time"],
            "references": [
                {
                    "source": d.metadata.get("source", "?"),
                    "page": d.metadata.get("page", "?"),
                    "preview": d.page_content[:120],
                }
                for d in docs
            ],
        }
        results.append(rec)
        save_partial()

        done = len(results) + skipped
        elapsed = time.time() - t_start
        eta = elapsed / done * (len(questions) - done) if done else 0
        print(
            f"[EVAL] {idx}/{len(questions)} {q['id']} 完成 "
            f"(total={perf['total']:.1f}s, 检索={perf['embedding'] + perf['vector_search'] + perf['rerank']:.2f}s, "
            f"生成={perf['llm_generation']:.1f}s, 改写={rw_time:.1f}s) "
            f"ETA {eta:.0f}s"
        )

    print(f"\n完成 {len(results)} 题（跳过 {skipped}）")
    if args.adaptive:
        n_g = sum(1 for r in results if r.get("mode_used") == "grounded")
        n_f = sum(1 for r in results if r.get("mode_used") == "fallback")
        print(f"[EVAL] 分级模式分布: grounded={n_g}, fallback={n_f}")
    return results


def summarize(results, args):
    rows = results
    if not rows:
        print("无有效结果")
        return {}

    subjects = {}
    for r in rows:
        subjects.setdefault(r["subject"], []).append(r)

    header = (
        f"{'科目':<10}{'回答质量':>10}{'要点命中':>10}{'平均total':>12}{'生成':>10}"
        if args.baseline
        else f"{'科目':<10}{'召回充分性':>10}{'回答质量':>10}{'要点命中':>10}{'平均total':>12}{'平均检索':>12}{'生成':>10}"
    )
    print(header)
    print("-" * len(header.encode("gbk", errors="replace")))
    summary = {}
    for subj, srows in subjects.items():
        line = {
            "subject": subj,
            "retrieval_sufficiency": _mean(srows, "retrieval_sufficiency"),
            "answer_quality": _mean(srows, "answer_quality"),
            "key_point_coverage": _mean(srows, "key_point_coverage"),
            "total": _mean(srows, "total"),
            "retrieval": _mean(srows, "retrieval"),
            "generation": _mean(srows, "generation"),
        }
        summary[subj] = line
        if args.baseline:
            print(
                f"{subj:<10}{str(line['answer_quality']):>10}{str(line['key_point_coverage']):>10}"
                f"{str(line['total']):>12}{str(line['generation']):>10}"
            )
        else:
            print(
                f"{subj:<10}{str(line['retrieval_sufficiency']):>10}{str(line['answer_quality']):>10}{str(line['key_point_coverage']):>10}"
                f"{str(line['total']):>12}{str(line['retrieval']):>12}{str(line['generation']):>10}"
            )

    totals = {
        "subject": "全部",
        "retrieval_sufficiency": _mean(rows, "retrieval_sufficiency"),
        "answer_quality": _mean(rows, "answer_quality"),
        "key_point_coverage": _mean(rows, "key_point_coverage"),
        "total": _mean(rows, "total"),
        "retrieval": _mean(rows, "retrieval"),
        "generation": _mean(rows, "generation"),
    }
    print("-" * len(header.encode("gbk", errors="replace")))
    if args.baseline:
        print(
            f"{totals['subject']:<10}{str(totals['answer_quality']):>10}{str(totals['key_point_coverage']):>10}"
            f"{str(totals['total']):>12}{str(totals['generation']):>10}"
        )
    else:
        print(
            f"{totals['subject']:<10}{str(totals['retrieval_sufficiency']):>10}{str(totals['answer_quality']):>10}{str(totals['key_point_coverage']):>10}"
            f"{str(totals['total']):>12}{str(totals['retrieval']):>12}{str(totals['generation']):>10}"
        )

    totals_p95 = {
        "total": _p95(rows, "total"),
        "retrieval": _p95(rows, "retrieval"),
        "generation": _p95(rows, "generation"),
    }
    print(
        f"\np95 延迟: total={totals_p95['total']}s, "
        f"检索={totals_p95['retrieval']}s, 生成={totals_p95['generation']}s"
    )
    summary["__overall__"] = totals
    summary["__p95__"] = totals_p95
    return summary


def _p95(rows, key):
    vals = sorted(r[key] for r in rows if r.get(key) is not None)
    if not vals:
        return None
    idx = min(len(vals) - 1, int(len(vals) * 0.95))
    return round(vals[idx], 2)


def main():
    parser = argparse.ArgumentParser(description="408 RAG 离线评测")
    parser.add_argument("--questions", default=os.path.join("data", "eval_questions.json"))
    parser.add_argument("--output", default=os.path.join("results"))
    parser.add_argument("--retrieval-only", action="store_true", help="只跑检索 + 召回充分性打分")
    parser.add_argument("--judge-backend", choices=["ollama", "api"], default=None)
    parser.add_argument("--judge-model", default=None)
    parser.add_argument("--gen-backend", choices=["ollama", "api"], default="ollama")
    parser.add_argument("--no-rewrite", action="store_true", help="关闭查询改写（A/B 对照用）")
    parser.add_argument("--baseline", action="store_true", help="纯模型基线：不检索，直接用模型知识回答")
    parser.add_argument("--adaptive", action="store_true", help="分级降级模式：检索置信度不足时回退纯模型回答")
    parser.add_argument("--limit", type=int, default=None, help="只跑前 N 题（冒烟测试）")
    parser.add_argument("--ids", default=None, help="只跑指定题目 id（逗号分隔，如 ds-01,co-08）")
    parser.add_argument("--resume", action="store_true", help="断点续跑，跳过已完成的题")
    parser.add_argument("--no-rerank", action="store_true", help="关闭 rerank：按融合分取 top-3、跳过门控（A/B 用）")
    parser.add_argument("--kb-root", default=None, help="覆盖向量库根目录（A/B 用，如 storage/chroma_bak_recursive）")
    args = parser.parse_args()

    if args.kb_root:
        Config.VECTOR_DB_PATH = os.path.normpath(args.kb_root)
        print(f"[EVAL] 向量库根目录覆盖为: {Config.VECTOR_DB_PATH}")

    # 读取库根目录的切块配置标记（rebuild_kb 写入），避免 meta 记录默认值
    kb_cfg = {}
    try:
        with open(
            os.path.join(Config.VECTOR_DB_PATH, "__kb_config__.json"), encoding="utf-8"
        ) as f:
            kb_cfg = json.load(f)
    except Exception:
        pass

    t0 = time.time()
    results = run_eval(args)
    summary = summarize(results, args)
    elapsed = time.time() - t0
    print(f"\n总耗时: {elapsed:.1f}s")

    os.makedirs(args.output, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(args.output, f"eval_results_{stamp}.json")
    latest_path = os.path.join(args.output, "eval_results_latest.json")
    payload = {
        "meta": {
            "mode": (
                "adaptive"
                if args.adaptive
                else "baseline"
                if args.baseline
                else "retrieval-only" if args.retrieval_only else "full"
            ),
            "rewrite": Config.QUERY_REWRITE_ENABLED,
            "rewrite_enabled_in_run": not args.no_rewrite and Config.QUERY_REWRITE_ENABLED,
            "rewrite_model": Config.QUERY_REWRITE_MODEL,
            "reranker": Config.RERANKER_MODEL,
            "rerank_enabled": (not args.no_rerank) and Config.RERANK_ENABLED,
            "no_rerank": args.no_rerank,
            "kb_root": Config.VECTOR_DB_PATH,
            "chunk_mode": kb_cfg.get("chunk_mode", Config.CHUNK_MODE),
            "chunk_size": kb_cfg.get("chunk_size", Config.CHUNK_SIZE),
            "chunk_overlap": kb_cfg.get("chunk_overlap", Config.CHUNK_OVERLAP),
            "reranker_fp16": Config.RERANKER_FP16,
            "embedding": Config.EMBEDDING_MODEL,
            "chat_model": Config.CHAT_MODEL,
            "chat_num_ctx": Config.CHAT_NUM_CTX,
            "gen_backend": args.gen_backend,
            "judge_backend": args.judge_backend or Config.EVAL_JUDGE_BACKEND,
            "judge_model": args.judge_model or Config.EVAL_JUDGE_MODEL,
            "top_k": Config.FINAL_TOP_K,
            "questions": len(results),
            "elapsed_s": round(elapsed, 1),
        },
        "summary": summary,
        "questions": results,
    }
    for p in (out_path, latest_path):
        with open(p, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存: {out_path}")


if __name__ == "__main__":
    main()
