"""重建 4 个学科知识点向量库（使用当前 Config 的切块模式）。

用法（在项目根目录，408rag 虚拟环境）:
    python scripts/rebuild_kb.py

行为:
    1. 旧库先整体备份到 storage/chroma_bak_recursive/<kb_name>
    2. 用 data/clean_md/ 下对应 md 文件 + 当前 CHUNK_MODE 重新切块并向量化
    3. 覆盖 storage/chroma/<kb_name>
"""
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from src.config import Config
from src.parser import DocumentParser
from src.retriever import KnowledgeBase


def main():
    # 重建阶段不需要 reranker（省显存），embedding 保持常驻避免反复加载
    Config.RERANK_ENABLED = False
    Config.EMBEDDING_KEEP_ALIVE = "30m"

    kb = KnowledgeBase()
    parser = DocumentParser()

    targets = sorted(
        f for f in os.listdir(Config.DATA_PATH)
        if f.endswith(".md") and "知识点" in f
    )
    print(f"[REBUILD] 切块模式: {Config.CHUNK_MODE} | 待重建: {targets}")

    chroma_root = os.path.abspath(Config.VECTOR_DB_PATH)
    bak_root = os.path.join("storage", "chroma_bak_recursive")

    for fn in targets:
        kb_name = os.path.splitext(fn)[0]
        src_dir = os.path.abspath(kb._kb_path(kb_name))
        if os.path.dirname(src_dir) != chroma_root:
            print(f"[SKIP] {kb_name}: 目标路径不在 {chroma_root} 下，跳过")
            continue

        # 1. 备份旧库（只备份一次）
        bak_dir = os.path.join(bak_root, kb_name)
        if os.path.isdir(src_dir) and not os.path.isdir(bak_dir):
            os.makedirs(os.path.dirname(bak_dir), exist_ok=True)
            shutil.copytree(src_dir, bak_dir)
            print(f"[BAK] 旧库已备份 -> {bak_dir}")

        # 2. 重新切块
        path = os.path.join(Config.DATA_PATH, fn)
        docs = parser.parse(path)
        if not docs:
            print(f"[SKIP] {kb_name}: 解析结果为空")
            continue

        # 3. 重建（先清掉旧库目录，避免 Chroma 复用旧数据）
        if os.path.isdir(src_dir):
            shutil.rmtree(src_dir)
        n = kb.save_persistent(kb_name, docs)
        print(f"[OK] {kb_name}: {n} chunks")
        kb.db = None
        kb._chunk_docs = []

    print("[REBUILD] 完成")


if __name__ == "__main__":
    main()
