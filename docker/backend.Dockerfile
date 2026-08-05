# CacheFlow408 后端（FastAPI + RAG 检索/重排）
# 镜像含 torch CUDA 运行时（约 6~7 GB），8GB 显存可跑 rerank；CPU 机器请改用
# docker-compose.cpu.yml（自动关闭 rerank 与查询改写）。
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

WORKDIR /app

# OCR（opencv）运行所需系统库
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*

# 先装 torch（CUDA 12.8 版，与本机已验证版本一致；单源安装避免多源哈希冲突）
COPY docker/requirements-torch.txt /tmp/requirements-torch.txt
RUN pip install --index-url https://download.pytorch.org/whl/cu128 -r /tmp/requirements-torch.txt

# 再装其余依赖（利用 Docker 层缓存，代码改动不重复装包）
COPY docker/requirements-backend.txt /tmp/requirements-backend.txt
RUN pip install -r /tmp/requirements-backend.txt

# 拷贝后端与核心库
COPY backend/ ./backend/
COPY src/ ./src/

EXPOSE 8000

# OLLAMA_BASE_URL 由 docker-compose 注入（指向 ollama 服务）
CMD ["uvicorn", "backend.api:app", "--host", "0.0.0.0", "--port", "8000"]
