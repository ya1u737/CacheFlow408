"""重建 4 个学科知识点向量库（使用当前 Config 的切块模式）。

用法（在项目根目录，408rag 虚拟环境）:
    python scripts/rebuild_kb.py
    python scripts/rebuild_kb.py --chunk-size 400 --overlap 150 --kb-root storage/chroma_s400

行为:
    1. 旧库先整体备份到 storage/chroma_bak_recursive/<kb_name>
    2. 用 data/clean_md/ 下对应 md 文件 + 当前 CHUNK_MODE 重新切块并向量化
    3. 覆盖 storage/chroma/<kb_name>
"""
import argparse
import json
import os
import shutil
import sys
import time
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from src.config import Config
from src.parser import DocumentParser
from src.retriever import KnowledgeBase


LOG_PATH = os.path.join("results", "rebuild_progress.log")


def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def main():
    parser = argparse.ArgumentParser(description="重建 4 个学科知识点向量库（可指定切块参数与库根目录）")
    parser.add_argument("--chunk-size", type=int, default=None, help="切块大小（覆盖 Config.CHUNK_SIZE）")
    parser.add_argument("--overlap", type=int, default=None, help="切块重叠（覆盖 Config.CHUNK_OVERLAP）")
    parser.add_argument("--kb-root", default=None, help="向量库根目录（覆盖 Config.VECTOR_DB_PATH，评测用）")
    args = parser.parse_args()
    if args.chunk_size:
        Config.CHUNK_SIZE = args.chunk_size
    if args.overlap is not None:
        Config.CHUNK_OVERLAP = args.overlap
    if args.kb_root:
        Config.VECTOR_DB_PATH = args.kb_root

    # 重建阶段不需要 reranker（省显存），embedding 保持常驻避免反复加载
    Config.RERANK_ENABLED = False
    Config.EMBEDDING_KEEP_ALIVE = 1800  # 30 分钟（langchain 接受整数秒，不接受 "30m"）

    kb = KnowledgeBase()
    parser = DocumentParser()

    targets = sorted(
        f for f in os.listdir(Config.DATA_PATH)
        if f.endswith(".md") and "知识点" in f
    )
    log(
        f"[REBUILD] 切块模式: {Config.CHUNK_MODE} | "
        f"chunk_size={Config.CHUNK_SIZE} overlap={Config.CHUNK_OVERLAP} | "
        f"库根: {Config.VECTOR_DB_PATH} | 待重建: {targets}"
    )

    chroma_root = os.path.abspath(Config.VECTOR_DB_PATH)
    bak_root = os.path.join("storage", "chroma_bak_recursive")

    try:
        for fn in targets:
            kb_name = os.path.splitext(fn)[0]
            src_dir = os.path.abspath(kb._kb_path(kb_name))
            if os.path.dirname(src_dir) != chroma_root:
                log(f"[SKIP] {kb_name}: 目标路径不在 {chroma_root} 下，跳过")
                continue

            # 1. 备份旧库（只备份一次）
            bak_dir = os.path.join(bak_root, kb_name)
            if os.path.isdir(src_dir) and not os.path.isdir(bak_dir):
                os.makedirs(os.path.dirname(bak_dir), exist_ok=True)
                shutil.copytree(src_dir, bak_dir)
                log(f"[BAK] 旧库已备份 -> {bak_dir}")

            # 2. 重新切块
            path = os.path.join(Config.DATA_PATH, fn)
            docs = parser.parse(path)
            if not docs:
                log(f"[SKIP] {kb_name}: 解析结果为空")
                continue

            # 3. 重建（先清掉旧库目录，避免 Chroma 复用旧数据）
            if os.path.isdir(src_dir):
                shutil.rmtree(src_dir)
            n = None
            last_err = None
            for attempt in range(1, 5):
                try:
                    # 每次重试换新的 embedding 连接，规避 Ollama runner 偶发断连
                    if attempt > 1:
                        kb = KnowledgeBase()
                    n = kb.save_persistent(kb_name, docs)
                    break
                except Exception as e:
                    last_err = e
                    log(
                        f"[RETRY] {kb_name} 第 {attempt} 次失败: "
                        f"{type(e).__name__}: {str(e)[:160]}"
                    )
                    time.sleep(5)
            if n is None:
                raise RuntimeError(f"{kb_name} 重建失败: {last_err}")
            log(f"[OK] {kb_name}: {n} chunks")
            kb.db = None
            kb._chunk_docs = []
        log("[REBUILD] 完成")
        # 写入该库根目录的切块配置标记，供评测/复盘读取（避免 meta 记错参数）
        marker = os.path.join(Config.VECTOR_DB_PATH, "__kb_config__.json")
        with open(marker, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "chunk_mode": Config.CHUNK_MODE,
                    "chunk_size": Config.CHUNK_SIZE,
                    "chunk_overlap": Config.CHUNK_OVERLAP,
                    "updated": time.strftime("%Y-%m-%d %H:%M:%S"),
                },
                f,
                ensure_ascii=False,
                indent=2,
            )
        log(f"[REBUILD] 已写入切块配置标记: {marker}")
    except Exception:
        log("[REBUILD] 失败:\n" + traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
