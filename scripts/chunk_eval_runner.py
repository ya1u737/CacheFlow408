"""按切块参数矩阵跑完整评测：重建对应向量库 -> 80 题完整评测（rerank + 门控）。

用法（项目根目录，408rag 环境）：
    python scripts/chunk_eval_runner.py

每个配置输出到 results/leg_<tag>/，已完成的配置会自动跳过（断点续跑）。
基准：results/eval_results_80_hybrid_oldchunk_complete.json（chunk 800/overlap 150）。
"""

import argparse
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable

# 评测矩阵：(chunk_size, overlap, 库根目录, 结果目录 tag)
# 800/150 为产品默认，已有基线结果（eval_results_80_hybrid_oldchunk_complete.json），不重复评测
CONFIGS = [
    (400, 150, "storage/chroma_s400", "chunk400"),
    (1200, 150, "storage/chroma_s1200", "chunk1200"),
]


def done(tag):
    return os.path.exists(
        os.path.join(ROOT, "results", f"leg_{tag}", "eval_results_latest.json")
    )


def run(cmd, log_path):
    print(f"\n[RUN] {' '.join(cmd)}", flush=True)
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"\n===== {os.path.basename(log_path)} {cmd} =====\n")
        f.flush()
        subprocess.run([PY] + cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT, check=True)


def main():
    parser = argparse.ArgumentParser(description="切块参数矩阵评测")
    parser.add_argument("--configs", default="all", help="逗号分隔 tag 子集，如 chunk400,chunk1200")
    args = parser.parse_args()
    wanted = args.configs.split(",") if args.configs != "all" else None

    for size, overlap, root, tag in CONFIGS:
        if wanted and tag not in wanted:
            continue
        if done(tag):
            print(f"[SKIP] {tag} 已完成", flush=True)
            continue
        run(
            ["scripts/rebuild_kb.py", "--chunk-size", str(size), "--overlap", str(overlap), "--kb-root", root],
            os.path.join(ROOT, "results", f"leg_{tag}.log"),
        )
        run(
            [
                "evaluate.py",
                "--adaptive",
                "--resume",
                "--questions", "data/eval_questions_80.json",
                "--kb-root", root,
                "--output", os.path.join("results", f"leg_{tag}"),
            ],
            os.path.join(ROOT, "results", f"leg_{tag}.log"),
        )
        print(f"[DONE] {tag}（chunk {size}/overlap {overlap}）", flush=True)

    print("\n全部配置处理完成", flush=True)


if __name__ == "__main__":
    main()
