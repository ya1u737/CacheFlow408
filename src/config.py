import os
from dotenv import load_dotenv

# 加载项目根目录 .env（可选：DEEPSEEK_API_KEY / DEEPSEEK_API_MODEL）
load_dotenv()

class Config:
    # ==================== 路径配置 ====================
    DATA_PATH = "data/clean_md/"                # Markdown 文件存放目录
    VECTOR_DB_PATH = "storage/chroma/"          # Chroma 持久化目录（每个知识库一个子目录）

    # ==================== 本地 Ollama 聊天模型 ====================
    CHAT_MODEL = "qwen2.5:7b"              # 你当前运行的模型
    # 8GB 显存建议 8192；调大上下文会显著增加 KV 缓存显存占用
    CHAT_NUM_CTX = 8192

    # ==================== DeepSeek API 配置 ====================
    # 用户可在网页侧边栏填写自己的 API Key（运行时生效，仅存内存，不落盘）
    # 也可以在项目根目录 .env 中配置 DEEPSEEK_API_KEY=sk-xxx，启动时自动启用
    API_MODEL = os.getenv("DEEPSEEK_API_MODEL", "deepseek-chat")   # 可选 deepseek-chat / deepseek-reasoner
    API_BASE = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com")

    # ==================== Embedding 模型配置 ====================
    # 本地 Ollama Embedding（强烈推荐目前使用）
    EMBEDDING_MODEL = "bge-m3"
    # 8GB 显存下建议用完即释放，避免与 7b 生成模型、reranker 抢显存
    EMBEDDING_KEEP_ALIVE = "0"
    # 备选（任选其一）：
    # EMBEDDING_MODEL = "nomic-embed-text"
    # EMBEDDING_MODEL = "qwen3-embedding"    

    # RAG 检索参数
    CHUNK_SIZE = 800                     
    CHUNK_OVERLAP = 150
    # 切块模式: recursive=固定长度递归切块 | semantic=按标题/段落语义切块
    CHUNK_MODE = "semantic"              


    TOP_K = 4                            
    RETRIEVAL_TOP_K = 5                     
    FINAL_TOP_K = 3                        

    # ==================== 混合检索（BM25 词法 + 向量语义，RRF 融合）====================
    HYBRID_ENABLED = True                    # 是否启用 BM25 + RRF 混合检索
    DENSE_TOP_K = 10                         # 向量检索候选数（融合前）
    BM25_TOP_K = 10                          # BM25 候选数（融合前）
    RRF_K = 60                               # RRF 平滑常数
    RRF_DENSE_WEIGHT = 1.0                   # 向量路权重
    RRF_BM25_WEIGHT = 1.0                    # BM25 路权重

    # ==================== Rerank（Cross Encoder 重排序） ====================
    RERANK_ENABLED = True                        # 是否启用 Cross Encoder 重排序
    RERANKER_MODEL = r"D:\models\bge-reranker-v2-m3"
    RERANKER_FP16 = True                         # fp16 加载可省一半显存（质量几乎无损）

    # ==================== 分级降级（检索置信度门控）====================
    # 检索到的资料置信度不足时，不强行基于知识库回答，改用模型自身知识直接回答，
    # 避免"错误上下文带偏答案"。门控信号 = 重排器对候选的最高相关分。
    RAG_FALLBACK_ENABLED = True                  # 是否启用分级降级
    RAG_FALLBACK_THRESHOLD = 0.5                 # 最高重排分低于该值 → 纯模型回答（按评测校准）
    FALLBACK_NOTICE = "（知识库未检索到足够相关的内容，以下回答基于模型自身知识，仅供参考）"

    # ==================== Query Rewrite（查询改写）====================
    QUERY_REWRITE_ENABLED = True                 # 是否启用查询改写（轻量模型改写为更利于检索的查询）
    QUERY_REWRITE_MODEL = "qwen2.5:1.5b"         # 改写模型（本地 Ollama）
    QUERY_REWRITE_TIMEOUT = 20                   # 改写超时（秒），超时回退原问题

    # ==================== 评测打分（Judge）配置 ====================
    EVAL_JUDGE_BACKEND = "ollama"                # 裁判后端: ollama / api（DeepSeek 等）
    EVAL_JUDGE_MODEL = "qwen2.5:7b"              # 裁判模型；api 模式下可设为 deepseek-chat 等

    FALLBACK_PROMPT = """
你是 KnowMate-408，一个计算机408考研辅导助手（数据结构、操作系统、计算机网络、计算机组成原理）。

【说明】
当前知识库未检索到足够相关的资料，请直接基于你自己的知识回答下面的问题。
回答要准确、完整，突出408考试重点；如果是选择题，说明正确选项及原因，并简要解释错误选项。

====================
历史对话
====================
{chat_history}

====================
用户问题
====================
{question}

请直接回答：
"""

    # ==================== Prompt 模板（ ====================
    PROMPT_TEMPLATE = """
你是 KnowMate-408，一个基于用户资料库的计算机408考研辅导助手。

你的任务：
仅根据【参考上下文】回答用户问题，帮助用户复习：
- 数据结构
- 操作系统
- 计算机网络
- 计算机组成原理

====================
核心规则（必须遵守）
====================

1. 知识来源限制

回答必须以【参考上下文】为主要依据。

禁止：
- 使用你自身记忆补充参考上下文中不存在的内容。
- 编造教材、公式、定义、结论。
- 在上下文不足时进行猜测。

如果参考上下文无法支持回答：

请直接回答：

“当前知识库没有找到相关内容，请上传相关资料或补充知识库。”

不要继续扩展解释。


====================
问题范围限制
====================

你只能回答：

- 数据结构
- 操作系统
- 计算机网络
- 计算机组成原理
- 与408复习直接相关的问题

如果用户询问无关内容：

例如：
- 天气
- 娱乐新闻
- 日常聊天
- 股票投资
- 医疗法律
- 非408技术问题

请回答：

“抱歉，我是408考研知识库助手，只负责数据结构、操作系统、计算机网络、计算机组成原理相关问题。”


====================
回答要求
====================

回答时：

1. 先给出结论。
2. 再解释原因。
3. 突出408考试重点。
4. 标注容易混淆的概念。
5. 必要时给出简单例子。

使用Markdown格式：
- 使用标题
- 使用列表
- 使用表格（必要时）

不要输出：
- 思考过程
- 与问题无关的扩展内容
- “作为AI……”等描述。


====================
引用规则
====================

回答内容应该能够在参考上下文中找到依据。

不要说：
- “我的训练数据表明”
- “我认为”
- “根据我的知识”

可以说：
- “根据资料中的描述”
- “资料中指出”


====================
历史对话
====================
{chat_history}


====================
参考上下文
====================
{context}


====================
用户问题
====================
{question}


请直接回答：
"""
