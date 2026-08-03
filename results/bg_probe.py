import json, os, sys
sys.path.insert(0, ".")
from src.config import Config
from langchain_ollama import OllamaEmbeddings
out = {
    "OLLAMA_HOST": os.environ.get("OLLAMA_HOST"),
    "HTTP_PROXY": os.environ.get("HTTP_PROXY"),
    "HTTPS_PROXY": os.environ.get("HTTPS_PROXY"),
    "ALL_PROXY": os.environ.get("ALL_PROXY"),
}
try:
    e = OllamaEmbeddings(model=Config.EMBEDDING_MODEL, keep_alive=1800)
    v = e.embed_query("probe")
    out["embed_ok"] = True
    out["dim"] = len(v)
except Exception as ex:
    out["embed_ok"] = False
    out["error"] = repr(ex)
with open("results/bg_probe_result.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
