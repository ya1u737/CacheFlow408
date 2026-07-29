import os

class Config:
    # ==================== 路径配置 ====================
    DATA_PATH = "data/clean_md/"                # Markdown 文件存放目录
    VECTOR_DB_PATH = "vector_db/"           

    # ==================== 本地 Ollama 聊天模型 ====================
    CHAT_MODEL = "qwen2.5:7b"              # 你当前运行的模型

    # ==================== DeepSeek API 配置 ====================
    USE_API = False
    API_MODEL = "deepseek-reasoner"
    API_KEY = ""
    API_BASE = "https://api.deepseek.com"

    # ==================== Embedding 模型配置 ====================
    # 本地 Ollama Embedding（强烈推荐目前使用）
    EMBEDDING_MODEL = "bge-m3"             
    
    # RAG 检索参数
    CHUNK_SIZE = 800                     
    CHUNK_OVERLAP = 150


    TOP_K = 4                            
    RETRIEVAL_TOP_K = 5                     
    FINAL_TOP_K = 3                        

    # ==================== Rerank ====================
    RERANKER_MODEL = r"D:\models\bge-reranker-v2-m3"

    # ==================== Prompt 模板 ====================
    PROMPT_TEMPLATE = """你是一位专业、严谨、有十年教学经验的 408 考研导师（涵盖数据结构、操作系统、计算机网络、计算机组成原理）。
请严格基于上下文信息回答问题，结合历史对话，重点突出核心考点、易混点、经典解题思路。
回答要逻辑清晰、条理分明，适当使用 Markdown 列表、加粗、编号。
必须优先依据知识库回答。

如果知识库没有提供相关信息：
请明确说明：
“当前知识库没有找到相关内容。”

不要使用模型自身记忆替代知识库内容。
不要回答与这四门课无关的问题，如果用户提问，请回答“抱歉，我只专注于数据结构、操作系统、计算机网络、计算机组成原理四门课程的考研辅导”。

【对话历史】
{chat_history}

【参考上下文】
{context}

【当前问题】
{question}

请直接开始回答，不要重复问题："""