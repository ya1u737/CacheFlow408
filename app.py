import streamlit as st
import os
from src.config import Config
from src.parser import DocumentParser
from src.retriever import KnowledgeBase
from src.generator import AnswerGenerator

# 1. 基础配置
st.set_page_config(
    page_title="KnowMate Assistant",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)



st.markdown("""
<style>
/* === 全局背景 === */
[data-testid="stAppViewContainer"] {
    background-color: #131314;
    color: #E3E3E3;
}

/* === 弱化默认 header === */
[data-testid="stHeader"] {
    background: rgba(19, 19, 20, 0.25) !important;
    backdrop-filter: blur(4px);
    height: 3.5rem;
    min-height: 3.5rem;
    z-index: 800 !important;
    border-bottom: none;
}

[data-testid="stDecoration"] {
    display: none !important;
}

/* === 固定顶栏（降低 z-index，让 toggle 优先）=== */
.top-banner {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    height: 56px;
    background-color: rgba(30, 31, 32, 0.92);
    backdrop-filter: blur(12px);
    border-bottom: 1px solid rgba(255, 255, 255, 0.15);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 9980 !important;           /* 降低一点 */
    pointer-events: none;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.35);
}

.top-banner h1 {
    font-size: 1.28rem;
    color: #FFFFFF;
    font-weight: 600;
    margin: 0;
    padding: 0 20px;
    text-align: center;
    text-shadow: 0 1px 4px rgba(0, 0, 0, 0.6);
    pointer-events: auto;
}

/* === 重点修复：侧边栏 Toggle 按钮（左上角 hamburger）=== */
[data-testid="stSidebarCollapsedControl"] {
    position: fixed !important;
    top: 10px !important;
    left: 16px !important;              /* 稍微右移，避免被 banner 完全压住 */
    z-index: 10020 !important;          /* 最高优先级 */
    background-color: rgba(40, 42, 45, 0.98) !important;
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 8px;
    padding: 6px 10px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
    transition: all 0.2s ease;
    color: #E3E3E3;
}

[data-testid="stSidebarCollapsedControl"]:hover {
    background-color: rgba(55, 58, 62, 0.98) !important;
    transform: scale(1.05);
}

/* 主内容下移 */
.block-container,
.stMainBlockContainer,
.main {
    padding-top: 110px !important;
}

/* 聊天区域 & 输入框（保持原样） */
[data-testid="stChatMessage"] {
    max-width: 820px;
    margin: 0 auto;
}

[data-testid="stChatMessage"]:nth-child(even) {
    background-color: rgba(30, 31, 32, 0.85);
    border-radius: 14px;
    padding: 12px 18px;
    border: 1px solid rgba(255, 255, 255, 0.1);
}

[data-testid="stChatInput"] {
    max-width: 820px;
    margin: 20px auto 30px auto;
    border-radius: 24px;
    border: 1px solid rgba(255, 255, 255, 0.2);
    background-color: rgba(30, 31, 32, 0.85);
    backdrop-filter: blur(10px);
}

/* 侧边栏 */
[data-testid="stSidebar"] {
    background-color: #1E1F20;
    border-right: 1px solid #333537;
}

[data-testid="stSidebarUserContent"] {
    padding-top: 90px !important;
}

/* 动画 */
@keyframes fadeIn {
    from { opacity: 0; transform: translateY(-8px); }
    to { opacity: 1; transform: translateY(0); }
}

.top-banner {
    animation: fadeIn 0.4s ease-out;
}
</style>
""", unsafe_allow_html=True)

# 2. 初始化
if "messages" not in st.session_state:
    st.session_state.messages = []

if "components_loaded" not in st.session_state:
    st.session_state.parser = DocumentParser()
    st.session_state.kb = KnowledgeBase()
    st.session_state.generator = AnswerGenerator()
    st.session_state.components_loaded = True

# 3. 侧边栏 - 添加自定义展开/收起按钮
with st.sidebar:
    # ==================== 模型切换 ====================
    st.markdown("### 🤖 模型选择")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("☁️ DeepSeek",
                     use_container_width=True,
                     type="primary" if st.session_state.generator.current_mode == "api" else "secondary"):
            st.session_state.generator.switch_mode("api")
            st.rerun()

    with col2:
        if st.button("🖥️ 本地 Ollama",
                     use_container_width=True,
                     type="primary" if st.session_state.generator.current_mode == "ollama" else "secondary"):
            st.session_state.generator.switch_mode("ollama")
            st.rerun()

    current_model = "DeepSeek (云端)" if st.session_state.generator.current_mode == "api" else f"本地 Ollama ({Config.CHAT_MODEL})"
    st.caption(f"**当前使用：** {current_model}")
    # === 新增：自定义醒目的侧边栏控制按钮 ===
    col1, col2 = st.columns([1, 4])


    st.markdown("### 🎓 资料库管理")
    st.divider()

    preset_docs = {
        "数据结构_知识点": "数据结构_知识点.md",
        "操作系统_知识点": "操作系统_知识点.md",
        "计算机网络_知识点": "计算机网络_知识点.md",
        "组成原理_知识点": "组成原理_知识点.md",
    }
    selected = st.selectbox("选择预设讲义", options=["未选择"] + list(preset_docs.keys()))

    if selected != "未选择" and st.button("一键激活", use_container_width=True):

        path = os.path.join(Config.DATA_PATH, preset_docs[selected])

        print("文件路径:", path)

        if os.path.exists(path):

           

            docs = st.session_state.parser.parse_txt(path)

            print("解析文档数量:", len(docs))

            if docs:
                print("第一段内容:")
                print(docs[0].page_content[:200])

            else:
                print("❌ parser返回空列表")

            st.session_state.kb.add_documents(docs)

            st.success("考点已同步内存")



    st.divider()
    uploaded_file = st.file_uploader(
        "上传资料（支持 PDF / TXT /DOCX）",
        type=["pdf", "txt","docx"]
    )

    if uploaded_file:
        if uploaded_file.type == "application/pdf":
            docs = st.session_state.parser.parse_pdf(uploaded_file)

        elif uploaded_file.type == "text/plain":
            docs = st.session_state.parser.parse_txt(uploaded_file)

        elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            docs = st.session_state.parser.parse_docx(uploaded_file)

        else:
            st.error("不支持该文件类型")
            docs = []

        if docs:
            # 确保每个 chunk 都有 source 和 page 信息
            for doc in docs:
                if "source" not in doc.metadata or not doc.metadata["source"]:
                    doc.metadata["source"] = uploaded_file.name
                if "page" not in doc.metadata:
                    doc.metadata["page"] = "N/A"

            st.session_state.kb.add_documents(docs)
            st.success("资料已加载")

    st.markdown('<div style="height: 20vh;"></div>', unsafe_allow_html=True)
    if st.button("🗑️ 清空当前对话", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# 4. 自定义顶栏
st.markdown('<div class="top-banner"><h1>408 RAG Pro | 考研智能导师</h1></div>', unsafe_allow_html=True)

# 历史对话
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 输入与回答逻辑
if prompt := st.chat_input("在此提问 408 考点..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        import time as _t
        _t0 = _t.time()
        relevant_docs = st.session_state.kb.search(prompt)
        _t_ret_total = _t.time() - _t0

        res_box = st.empty()
        _t1 = _t.time()
        full_res = res_box.write_stream(
            st.session_state.generator.generate(
                prompt, relevant_docs, st.session_state.messages[:-1]
            )
        )
        _t_gen = _t.time() - _t1
        _t_total = _t.time() - _t0
        print(f'[PERF] Generation: {_t_gen:.2f}s')
        print(f'[PERF] Total: {_t_total:.2f}s')


        if relevant_docs:
            with st.expander("📚 检索知识点"):

                for idx, doc in enumerate(relevant_docs, start=1):

                    src = doc.metadata.get("source", "未知来源")
                    page = doc.metadata.get("page", "N/A")

                    content = doc.page_content.strip()

                    # PDF符号处理
                    content = content.replace("", " ")
                    content = content.replace("\n", " ")

                    # 去除多余空格
                    content = " ".join(content.split())


                    # 只取前15个字作为知识点摘要
                    preview = content[:15]

                    if len(content) > 15:
                        preview += "..."


                    # 一行显示
                    st.write(
                        f"📌 {idx}. {preview}"
                    )

                    # 来源单独一行
                    st.caption(
                        f"📄 {src}  P{page}"
                    )