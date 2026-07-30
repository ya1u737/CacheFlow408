# 🎓 KnowMate-RAG Assistant
> **Modern, Local-First Knowledge Base Assistant with DeepSeek & Vue 3**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Vue 3](https://img.shields.io/badge/frontend-Vue%203-brightgreen.svg)](https://vuejs.org/)
[![FastAPI](https://img.shields.io/badge/backend-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Powered by Ollama](https://img.shields.io/badge/LLM-Ollama-orange.svg)](https://ollama.com/)

**KnowMate** 是一个采用**前后端分离架构**的高性能本地 RAG（检索增强生成）系统。专为 408 计算机考研、专业学术资料等强知识场景设计，支持精准的文档切片、向量检索、重排序（Rerank）以及流式打字机响应。

---
## DEMO



<img src="./assets/demo.png" width="800">
## 🌟 Core Features

- **🚀 前后端分离架构**：基于 **Vue 3 + Vite + Element Plus** 的极简美观现代 UI，搭配 **FastAPI** 高性能异步后端。
- **⚡ 流式 SSE 打字机**：支持流式生成回答（Server-Sent Events）
- **📚 智能知识库解析**：支持 Markdown、PDF、Word 及 TXT 解析，采用 `RecursiveCharacterTextSplitter` 做到精准切片。
- **🔍 混合检索与重排**：**Chroma + bge-m3** 向量检索，配合 **bge-reranker-v2-m3** 交叉编码器重排序，检索精度极高。
- **🔒 纯本地私有化**：敏感数据零上传，本地 Ollama 模型推理 + 本地向量数据库存储，确保数据绝对安全。

---

## 🏗️ Architecture
┌──────────────────────────────────────────────────────────┐
│              Vue 3 + Element Plus Frontend               │
│      (Chat UI / Knowledge Base Mgmt / Stream Console)    │
└────────────────────────────┬─────────────────────────────┘
│ REST API / SSE Stream
┌────────────────────────────▼─────────────────────────────┐
│                    FastAPI Backend                       │
│ ┌──────────────────────────────────────────────────────┐ │
│ │                  RAG Pipeline Core                   │ │
│ │  ① Document Parsing (PyMuPDF / Markdown)             │ │
│ │  ② Text Chunking (LangChain Splitters)               │ │
│ │  ③ Vector Retrieval (ChromaDB + Ollama bge-m3)       │ │
│ │  ④ Reranking (bge-reranker-v2-m3)                    │ │
│ │  ⑤ LLM Context Assembly & SSE Generation             │ │
│ └──────────────────────────────────────────────────────┘ │
└────────────────────────────┬─────────────────────────────┘
│ Local IPC / Cloud API
┌────────────────────────────▼─────────────────────────────┐
│          Ollama (Qwen2.5 / DeepSeek) / DeepSeek API      │
└──────────────────────────────────────────────────────────┘
### Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Vue 3 (Composition API), Vite, Element Plus, Axios, Pinia |
| **Backend API** | Python 3.11+, FastAPI, Uvicorn, SSE-Starlette |
| **Document Parsing** | PyMuPDF, langchain-text-splitters |
| **Vector Database** | ChromaDB + `bge-m3` (Ollama Embeddings) |
| **Reranker** | `bge-reranker-v2-m3` (Sentence-Transformers) |
| **LLM Inference** | Ollama (`qwen2.5:7b` / `deepseek-r1:14b`) or DeepSeek API |

---

## 🚀 Quick Start

### 1. Prerequisites

- Python 3.11+
- Node.js 18+
- [Ollama](https://ollama.com/)

### 2. Model Preparation

```bash
# Chat Model (Ollama)
ollama pull qwen2.5:7b
# or DeepSeek R1:
ollama pull deepseek-r1:14b

# Embedding Model
ollama pull bge-m3

# 1. Install Dependencies
pip install -r requirements.txt

# 2. Run FastAPI Backend Server
python -m uvicorn backend.api:app --reload --port 8000

# 1. Enter Frontend Directory
cd frontend

# 2. Install Dependencies
npm install

# 3. Start Development Server
npm run dev

📄 License
MIT License. See LICENSE for details.

World ❤️ Peace 