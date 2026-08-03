import streamlit as st
import os
import requests
from src.config import Config

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

API_BASE_URL = "http://localhost:8000"

# 2. 初始化
if "messages" not in st.session_state:
    st.session_state.messages = []

if "current_mode" not in st.session_state:
    st.session_state.current_mode = "ollama"

# 3. 侧边栏 - 添加自定义展开/收起按钮
with st.sidebar:
    # ==================== 模型切换 ====================
    st.markdown("### 🤖 模型选择")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("☁️ DeepSeek",
                     use_container_width=True,
                     type="primary" if st.session_state.current_mode == "api" else "secondary"):
            st.session_state.current_mode = "api"
            st.rerun()

    with col2:
        if st.button("🖥️ 本地 Ollama",
                     use_container_width=True,
                     type="primary" if st.session_state.current_mode == "ollama" else "secondary"):
            st.session_state.current_mode = "ollama"
            st.rerun()

    current_model = "DeepSeek (云端)" if st.session_state.current_mode == "api" else f"本地 Ollama ({Config.CHAT_MODEL})"
    st.caption(f"**当前使用：** {current_model}")

    # === DeepSeek API Key（用户自备，运行时填写）===
    if st.session_state.current_mode == "api":
        api_key_input = st.text_input(
            "DeepSeek API Key（自备）",
            type="password",
            placeholder="粘贴你的 API Key",
            key="km_api_key_input"
        )
        if st.button("保存并启用云端", use_container_width=True):
            key = (api_key_input or "").strip()
            resp = requests.post(
                f"{API_BASE_URL}/api/config/api_key",
                json={"api_key": key}
            )
            data = resp.json()
            if data.get("status") == "ok":
                st.success(data.get("message", "DeepSeek API 已启用"))
            else:
                st.error(data.get("message", data.get("detail", "启用失败")))

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

        filename = preset_docs[selected]

        resp = requests.post(f"{API_BASE_URL}/api/load_knowledge", params={"filename": filename})

        if resp.json().get("status") == "ok":
            st.success("考点已同步内存")
        else:
            st.error("加载失败")



    st.divider()
    uploaded_file = st.file_uploader(
        "上传资料（支持 PDF / TXT /DOCX）",
        type=["pdf", "txt","docx"]
    )

    if uploaded_file:
        files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
        resp = requests.post(f"{API_BASE_URL}/api/upload", files=files)
        data = resp.json()
        if data.get("status") == "ok":
            st.success("资料已加载")
        else:
            st.error(data.get("message", "上传失败"))

    st.markdown('<div style="height: 20vh;"></div>', unsafe_allow_html=True)
    if st.button("🗑️ 清空当前对话", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# 4. 自定义顶栏
st.markdown('<div class="top-banner"><h1>KnowMate RAG Assistant</h1></div>', unsafe_allow_html=True)

# 历史对话
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 输入与回答逻辑
if prompt := st.chat_input("在此提问 ..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        res_box = st.empty()
        full_res = ""
        references = []

        with requests.post(
            f"{API_BASE_URL}/api/query_stream",
            json={
                "question": prompt,
                "chat_history": st.session_state.messages[:-1],
                "mode": st.session_state.current_mode
            },
            stream=True
        ) as resp:
            for line in resp.iter_lines():
                if not line:
                    continue
                if line.startswith(b"data: "):
                    payload = line[6:]
                    import json
                    msg = json.loads(payload)
                    if msg["type"] == "token":
                        full_res += msg["data"]
                        res_box.markdown(full_res + "▌")
                    elif msg["type"] == "references":
                        references = msg["data"]
                    elif msg["type"] == "done":
                        break

        res_box.markdown(full_res)

        print("[PERF] 流式回答完成")

        if references:
            with st.expander("📚 检索知识点"):
                for idx, ref in enumerate(references, start=1):
                    preview = ref["preview"][:15] + "..." if len(ref["preview"]) > 15 else ref["preview"]
                    st.write(f"📌 {idx}. {preview}")
                    st.caption(f"📄 {ref['source']}  P{ref['page']}")

                    with st.expander("查看原文"):
                        st.write(ref["preview"])
