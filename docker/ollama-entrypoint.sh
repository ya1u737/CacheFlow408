#!/bin/sh
# 启动 Ollama 服务，并在后台按需拉取模型（首次启动下载约 6 GB，之后走缓存）。

set -e

# 启动 Ollama 服务
ollama serve &
SERVER_PID=$!

# 等待服务就绪
i=0
until ollama list >/dev/null 2>&1; do
    i=$((i + 1))
    if [ "$i" -gt 60 ]; then
        echo "[OLLAMA] 服务 60 秒内未就绪，继续运行（模型拉取可能失败）"
        break
    fi
    sleep 1
done

# 拉取配置的模型（逗号分隔）
if [ -n "$OLLAMA_MODELS_TO_PULL" ]; then
    for model in $(echo "$OLLAMA_MODELS_TO_PULL" | tr ',' ' '); do
        echo "[OLLAMA] 拉取模型: $model"
        ollama pull "$model" || echo "[OLLAMA] 拉取 $model 失败，稍后可手动执行: docker exec -it knowmate-ollama ollama pull $model"
    done
fi

# 保持前台进程
wait "$SERVER_PID"
