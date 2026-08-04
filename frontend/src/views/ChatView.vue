<template>
  <div class="chat-container" :style="{ '--primary-color': currentColor }">
    <!-- 📚 当前知识库状态卡片 -->
    <div class="kb-status-bar">
      <div class="kb-bubble">
        📚 {{ kbInfo.knowledge_base ? '当前知识库：' + kbInfo.knowledge_base : '暂无知识库' }}
      </div>
    </div>

    <!-- 消息对话列表区 -->
    <div class="message-list" ref="msgListRef" @scroll="handleScroll">
      <div v-for="(msg, i) in messages" :key="i" class="message-item">
        <!-- 用户消息 -->
        <div v-if="msg.role === 'user'" class="message-row user-row">
          <img 
            :src="userAvatarImg" 
            alt="User Avatar" 
            class="avatar user-avatar-img" 
          />
          <div class="message-bubble user-bubble">
            <p class="msg-text">{{ msg.content }}</p>
          </div>
        </div>

        <!-- AI 消息 -->
        <div v-else class="message-row assistant-row">
          <img 
          :src="botAvatarImg" 
          alt="Bot Avatar" 
          class="avatar ai-avatar-img" 
          />
          <div class="message-bubble assistant-bubble">
            <p class="msg-text ai-text">
              <template v-for="(seg, si) in citeSegments(msg.content)" :key="si">
                <span v-if="seg.type === 'cite'" class="cite-tag" @click="focusRef(i, seg.n)">{{ seg.text }}</span>
                <template v-else>{{ seg.text }}</template>
              </template>
            </p>

            <!-- 检索知识点参考（清晰调大版） -->
            <div v-if="msg.references && msg.references.length" class="refs-box" :data-i="i">
              <el-collapse v-model="msg.refsOpen">
                <el-collapse-item name="refs">
                  <template #title>
                    <div class="ref-summary-head">
                      <span class="ref-tag">📚 检索参考知识点</span>
                      <span class="ref-count">({{ msg.references.length }} 条来源)</span>
                    </div>
                  </template>

                  <!-- 原文列表容器 -->
                  <div class="ref-list">
                    <div v-for="(ref, j) in msg.references" :key="j" class="ref-node" :data-ref="j + 1">
                      <!-- 顶部元信息栏：来源 + 页码 + 展开开关 -->
                      <div class="ref-meta-bar" @click="ref.expanded = !ref.expanded">
                        <div class="meta-left">
                          <span class="meta-idx">[资料{{ j + 1 }}]</span>
                          <span class="meta-source">📄 {{ ref.source }}</span>
                          <span v-if="ref.heading" class="meta-heading">{{ ref.heading }}</span>
                        </div>
                        <div class="meta-action">
                          <span>{{ ref.expanded ? '收起原文' : '展开全文' }}</span>
                          <span class="action-symbol">{{ ref.expanded ? '▲' : '▼' }}</span>
                        </div>
                      </div>

                      <!-- 未展开时的单行摘要（清晰字体） -->
                      <div v-if="!ref.expanded" class="ref-preview-single">
                        📌 {{ ref.preview }}
                      </div>

                      <!-- 展开后的完整原文区块（清晰代码块风格） -->
                      <div v-else class="ref-full-codeblock">
                        <pre class="code-content">{{ ref.preview }}</pre>
                      </div>
                    </div>
                  </div>
                </el-collapse-item>
              </el-collapse>
            </div>

            <!-- 性能消耗统计 -->
            <p v-if="msg.perf" class="perf-info">
              ⚡ Query Rewrite: {{ msg.perf.rewrite }}s，Generation: {{ msg.perf.generation }}s，Total: {{ msg.perf.total }}s
            </p>
          </div>
        </div>
      </div>

      <!-- 思考加载状态 -->
      <div v-if="loading" class="loading-status">
        <span class="loading-icon">⏳</span> 正在检索与思考中...
      </div>
    </div>

    <!-- 🔥 新增：悬浮返回底部按钮（仅在用户向上滚动时显示） -->
    <div 
  v-if="userScrolledUp" 
  class="scroll-bottom-btn" 
  @click="forceScrollToBottom"
  title="返回底部"
>
  <span class="arrow-icon">↓</span>
</div>

    <!-- 底部输入框区域（固定在最下方） -->
    <div class="input-area">
      <div class="input-wrapper">
        <el-input
          v-model="question"
          placeholder="在此提问 ..."
          @keyup.enter="sendQuestion"
          :disabled="loading"
          size="large"
          class="custom-input"
        >
          <template #append>
            <el-button 
              @click="sendQuestion" 
              :disabled="loading" 
              type="primary"
              class="send-btn"
            >
              发送
            </el-button>
          </template>
        </el-input>
      </div>
    </div>
  </div>
</template>

<script>
import botAvatarImg from '../assets/bot_avatar.jpg'
import userAvatarImg from '../assets/user_avatar.png'
export default {
  data() {
    const sid = localStorage.getItem('km_session_id') || 'session_' + Date.now()
    localStorage.setItem('km_session_id', sid)
    return { 
      sessionId: sid,
      question: '', 
      messages: [], 
      loading: false,
      userScrolledUp: false,
      kbInfo: { knowledge_base: null, documents: [], chunk_count: 0 },
      mode: localStorage.getItem('km_llm_mode') || 'ollama',
      currentColor: localStorage.getItem('km_primary_color') || '#c8e338',
      userAvatarImg, 
      botAvatarImg
    }
  },
  mounted() {
    this.loadHistory()
    this.fetchKbInfo()
    // 监听侧边栏主题色切换
    window.addEventListener('km-color-change', this.onColorChange)
    // 监听侧边栏模型切换
    window.addEventListener('km-mode-change', this.onModeChange)
    this.currentColor = localStorage.getItem('km_primary_color') || '#c8e338'
  },
  beforeUnmount() {
    window.removeEventListener('km-color-change', this.onColorChange)
    window.removeEventListener('km-mode-change', this.onModeChange)
  },
    


  methods: {
    citeSegments(content) {
      if (!content) return [{ type: 'text', text: '' }]
      return String(content)
        .split(/(\[资料\d+\])/g)
        .filter(p => p !== '')
        .map(p => {
          const m = p.match(/^\[资料(\d+)\]$/)
          return m ? { type: 'cite', text: p, n: Number(m[1]) } : { type: 'text', text: p }
        })
    },

    focusRef(msgIdx, n) {
      const msg = this.messages[msgIdx]
      if (!msg || !msg.references || !msg.references.length) return
      msg.refsOpen = ['refs']
      this.$nextTick(() => {
        const el = document.querySelector(
          `.refs-box[data-i="${msgIdx}"] .ref-node[data-ref="${n}"]`
        )
        if (el) {
          el.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
          el.classList.remove('flash')
          void el.offsetWidth
          el.classList.add('flash')
          setTimeout(() => el.classList.remove('flash'), 1600)
        }
      })
    },

    onColorChange(e) {
      if (e.detail && e.detail.color) {
        this.currentColor = e.detail.color
      }
    },

    onModeChange(e) {
      if (e.detail && e.detail.mode) {
        this.mode = e.detail.mode
      }
    },
    
    async fetchKbInfo() {
      try {
        const r = await fetch('/api/status')
        const data = await r.json()
        this.kbInfo = {
          knowledge_base: data.knowledge_base || null,
          documents: data.documents || [],
          chunk_count: data.chunk_count || 0
        }
      } catch {
        this.kbInfo = { knowledge_base: null, documents: [], chunk_count: 0 }
      }
    },
      forceScrollToBottom() {
       this.userScrolledUp = false
       this.$nextTick(() => {
      const el = this.$refs.msgListRef
      if (el) {
        el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' }) // 丝滑平滑滚动
            }
          })
        },

      handleScroll() {
      const el = this.$refs.msgListRef
      if (!el) return
      
      // 距离底部超过 50px，说明用户手动往上滚了，暂停自动吸底
      const isAtBottom = el.scrollHeight - el.scrollTop - el.clientHeight <= 50
      this.userScrolledUp = !isAtBottom
    },

      // 改造原有的 scrollToBottom 方法
      scrollToBottom() {
        // 如果用户往上滚了，就不强制滚到底部！
        if (this.userScrolledUp) return
        
        this.$nextTick(() => {
          const el = this.$refs.msgListRef
          if (el) {
            el.scrollTop = el.scrollHeight
          }
        })
      },

    async loadHistory() {
      try {
        const r = await fetch(`/api/history?session_id=${this.sessionId}`)
        const data = await r.json()
        this.messages = (data.messages || []).slice(-15).map(m => ({
          ...m,
          refsOpen: []
        }))
        this.scrollToBottom()
      } catch {
        // 静默失败，不影响聊天
      }
    },


    async saveMessage(role, content, references = []) {
      try {
        await fetch('/api/history/save', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_id: this.sessionId,
            role, content, references
          })
        })
      } catch {}
    },
    async sendQuestion() {
      if (!this.question.trim()) return
      // 发送新消息时重置用户滚动状态，恢复自动吸底
      this.userScrolledUp = false
      const q = this.question
      this.question = ''
      this.messages.push({ role: 'user', content: q })
      this.saveMessage('user', q)
      this.loading = true

      const msgIndex = this.messages.length
      this.messages.push({ role: 'assistant', content: '', references: [], refsOpen: [], perf: null })

      this.scrollToBottom()

      const t0 = Date.now()
      try {
        const resp = await fetch('/api/query_stream', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            question: q,
            chat_history: this.messages.slice(0, -1).map(m => ({ role: m.role, content: m.content })),
            mode: this.mode
          })
        })
        const reader = resp.body.getReader()
        const decoder = new TextDecoder()
        let full = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          const lines = decoder.decode(value, { stream: true }).split('\n')
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const msg = JSON.parse(line.slice(6))
              if (msg.type === 'token') {
                full += msg.data
                this.messages[msgIndex].content = full
                this.scrollToBottom()
              } else if (msg.type === 'references') {
                this.messages[msgIndex].references = msg.data
              } else if (msg.type === 'error') {
                this.messages[msgIndex].content = '❌ ' + msg.data
              } else if (msg.type === 'performance') {
                const p = msg.data || {}
                const r1 = (v) => Math.round((v || 0) * 10) / 10
                this.messages[msgIndex].perf = {
                  rewrite: r1(p.query_process),
                  generation: r1(p.llm_generation),
                  total: r1(p.total)
                }
              } else if (msg.type === 'done') {
                if (!this.messages[msgIndex].perf) {
                  const total = Math.round(((Date.now() - t0) / 1000) * 10) / 10
                  this.messages[msgIndex].perf = { rewrite: 0, generation: total, total }
                }
              }
            }
          }
        }
      } catch (e) {
        this.messages[msgIndex].content = '❌ 请求失败: ' + e.message
      }
      this.loading = false
      // AI 回复完成后持久化 assistant 消息（带引用）
      const finalContent = this.messages[msgIndex]?.content || full
      if (finalContent && !finalContent.startsWith('❌')) {
        this.saveMessage('assistant', finalContent, this.messages[msgIndex]?.references || [])
      }
      this.scrollToBottom()
    }
  }
}
</script>

<style scoped>
/* 主容器：填满屏幕并 Flex 上下排列 */
/* 聊天框主容器 */
.chat-container {
  /* 核心主题色变量（侧边栏切换时动态覆盖） */
  --primary-color: #c8e338;
  position: relative;
  width: 100%;
  height: 100%;               /* 💡 使用 100% 继承 body 高度，避免 100vh 把输入框挤出屏幕 */
  display: flex;
  flex-direction: column;
  background-color: #1e1f23;  /* 保持与背景统一 */
  overflow: hidden;
}

/* 消息列表区（唯一的滚动区） */
.message-list {
  flex: 1;                    /* 自动占用除了顶部气泡和底部输入框外的所有剩余高度 */
  min-height: 0;              /* 💡 核心：必须加 min-height: 0，否则内容一长就会把底栏输入框挤掉！ */
  overflow-y: auto;           /* 保留对话列表自身的滚动条 */
  
  /* 取消左右 padding，让滚动条直接紧贴最右侧边界 */
  padding-top: 16px;
  padding-bottom: 16px;
  padding-left: 0;
  padding-right: 0;
}

/* 内部单条消息的左右边距 */
.message-item {
  padding-left: 20px;
  padding-right: 20px;
  margin-bottom: 16px;
}

/* 底部输入框固定区 */
.input-area {
  position: relative;
  flex-shrink: 0;             /* 💡 核心：防止输入框被 Flex 压缩或挤出屏幕 */
  padding: 16px 20px;
  background-color: #1e1f23;  /* 确保输入框背景不透明 */
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.message-row {
  display: flex;
  gap: 12px;
  align-items: flex-start;

  /* 👇 限制单条消息整体的宽带，并居中排布 */
  max-width: 800px;     /* 👈 推荐设为 750px ~ 850px */
  margin-left: auto;
  margin-right: auto;

  
}

.user-row {
  flex-direction: row-reverse;
}

.assistant-row {
  flex-direction: row;
}

/* 头像微调 */
.avatar {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  flex-shrink: 0;
}

.user-avatar {
  background-color: rgba(59, 130, 246, 0.2);
}

.ai-avatar {
  background-color: rgba(16, 185, 129, 0.2);
}

.message-bubble {
  max-width: 78%;
  padding: 12px 16px;
  border-radius: 12px;
  font-size: 15px;
  line-height: 1.6;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

/* 用户气泡 */
.user-bubble {
  background: linear-gradient(135deg, var(--primary-color), #1d4ed8);
  color: #ffffff;
  border-bottom-right-radius: 2px;
}

/* AI 气泡（深灰质感） */
.assistant-bubble {
  background-color: #1e1f23;
  border: 1px solid #2e3035;
  color: #ececec;
  border-bottom-left-radius: 2px;
}

.msg-text {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
}



/* ---------------- 检索参考知识点（清晰调大版） ---------------- */
.refs-box {
  margin-top: 12px;
}

:deep(.el-collapse) {
  border: none !important;
  background: transparent !important;
}

/* 折叠面板头部：字号 13px */
:deep(.el-collapse-item__header) {
  background-color: #1a1b1e !important;
  border: 1px solid #2d3036 !important;
  border-radius: 6px;
  height: 38px;
  line-height: 38px;
  padding: 0 12px;
  font-size: 13px;
  transition: all 0.2s ease;
}

:deep(.el-collapse-item__header:hover) {
  border-color: var(--primary-color) !important;
}

.ref-summary-head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ref-tag {
  color: #eff0ee;
  font-weight: 600;
  font-size: 13px;                             /* 👈 调大标题字号 */
}

.ref-count {
  color: #9ca3af;
  font-size: 12px;                             /* 👈 调大数量标注 */
}

:deep(.el-collapse-item__wrap) {
  background-color: transparent !important;
  border: none !important;
  padding-top: 8px;
}

:deep(.el-collapse-item__content) {
  padding: 0 !important;
}

/* 节点外框 */
.ref-node {
  background: #141518;
  border: 1px solid #2b2d35;
  border-radius: 6px;
  margin-bottom: 8px;
  overflow: hidden;
  transition: border-color 0.2s ease;
}

.ref-node:hover {
  border-color: #3f424e;
}

/* 元信息栏（包含来源、页码、按钮） */
.ref-meta-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;                          /* 👈 增加内边距，视觉更好看 */
  background: #1d1f24;
  cursor: pointer;
  user-select: none;
}

.meta-left {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;                             /* 👈 来源字号调大到 13px */
}

.meta-idx {
  color: var(--primary-color);
  font-weight: 700;
}

.meta-source {
  color: #e5e7eb;
  font-weight: 500;
}

.meta-heading {
  color: #9ca3af;
  font-size: 12px;
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cite-tag {
  color: var(--primary-color);
  font-weight: 600;
  cursor: pointer;
  border-bottom: 1px dashed var(--primary-color);
  padding: 0 1px;
  user-select: none;
}

.cite-tag:hover {
  filter: brightness(1.15);
}

.ref-node.flash {
  border-color: var(--primary-color) !important;
  box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.06);
  transition: border-color 0.2s ease;
}

.meta-action {
  display: flex;
  align-items: center;
  gap: 4px;
  color: var(--primary-color);                 /* 👈 改用主题色高亮按钮 */
  font-size: 12px;                             /* 👈 按钮字号调大到 12px */
  font-weight: 600;
}

.action-symbol {
  font-size: 10px;
}

/* 单行摘要预览：字号 13px */
.ref-preview-single {
  padding: 8px 12px;
  font-size: 13px;                             /* 👈 未展开预览字号调大到 13px */
  color: #9ca3af;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
/* 展开后的原文文本区：现代浅色规范风格 */
.ref-full-codeblock {
  padding: 14px 16px;
  background: #1e1f23; /* 项目主体深灰色 */
  border: 1px solid var(--primary-color); /* 随系统主题色变化 */
  border-radius: 6px; /* 加上轻微圆角，瞬间消除僵硬感 */
  
  /* 换成标准无衬线字体，优雅清晰 */
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  font-size: 14px; /* 13px 稍微偏小，14px 读起来最舒适 */
  line-height: 1.6; /* 黄金行高，提升可读性 */
  color: #d1d5db; /* 深色背景下的浅灰文字 */
}
.code-content {
  margin: 0;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 13px;                             /* 👈 展开后的原文正文字号 13px */
  line-height: 1.7;                             /* 👈 加大行高，更易阅读 */
  color: #d1d5db;                              /* 👈 使用更亮的灰白色 */
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 240px;                           /* 👈 可视高度加大到 240px */
  overflow-y: auto;
}

/* 美化滚动条 */
.code-content::-webkit-scrollbar {
  width: 4px;
}

.code-content::-webkit-scrollbar-thumb {
  background: #33363f;
  border-radius: 2px;
}








/* 底部固定输入框区域 */
.input-area {
  flex-shrink: 0;
  padding: 16px 20px 24px;
  background-color: #131417;
}

/* 外层容器统一接管圆角和溢出裁切 */
.input-wrapper {
  max-width: 800px;
  margin: 0 auto;
  background-color: #1e1f23;
  border-radius: 12px;         /* 适当加大圆角，更现代化 */
  border: 1px solid #2e3035;   /* 补上一圈细边框，增强立体感 */
  overflow: hidden;             /* 关键：防止内部直角元素溢出 */
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
  display: flex;
  align-items: center;
}

/* 清除 Element Plus 内部缝隙与背景冲突 */
:deep(.custom-input) {
  border: none !important;
}

:deep(.custom-input .el-input__wrapper) {
  background-color: transparent !important;
  box-shadow: none !important;
  padding: 6px 16px;
}

/* 用户输入的文字为白色 */
:deep(.custom-input .el-input__inner) {
  color: #ffffff !important;        /* 输入框内文字改为纯白 */
  font-size: 15px;                    /* 可选：适当字号让文本更清晰 */
}

/* 未输入时的占位提示词 (Placeholder) 颜色 */
:deep(.custom-input .el-input__inner::placeholder) {
  color: #6b7280 !important;        
}
/* 修复右侧 append 区域的直角拼接 */
:deep(.custom-input .el-input-group__append) {
  background-color: transparent !important;
  border: none !important;
  box-shadow: none !important;
  padding: 0 30px 0 12px !important; /* 右侧改为 12px 留出气口，不再紧贴最右边 */
  display: flex !important;
  align-items: center !important;
}
.send-btn {
  background-color: var(--primary-color) !important;
  border-color: var(--primary-color) !important;
  color: #000000 !important; 
  font-weight: 700;
  border-radius: 5px !important;
}

.send-btn:hover {
  background-color: #1d4ed8 !important;
}

.scroll-bottom-btn {
  position: absolute;
  bottom: 85px;
  left: 50%;
  /* 1. 默认状态必须是 -50% */
  transform: translateX(-50%); 
  
  width: 36px;
  height: 36px;
  border-radius: 50%;
  
  /* 毛玻璃质感 */
  background: rgba(255, 255, 255, 0.2); 
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.25);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);

  display: flex;
  align-items: center;
  justify-content: center;
  color: #ffffff;
  cursor: pointer;
  z-index: 10;
  
  /* 2. 优化动画属性：只对 background 和 transform 做动画，避免影响其他属性 */
  transition: background 0.2s ease, transform 0.2s ease;
  user-select: none;
}

.scroll-bottom-btn:hover {
  background: rgba(255, 255, 255, 0.35);
  /* 3. hover 保持 -50%，只改变 Y 轴微抬 */
  transform: translateX(-50%) translateY(-2px); 
}
.arrow-icon {
  font-size: 16px;
  font-weight: bold;
  line-height: 1;
}

/* 顶部悬空容器 */
.kb-status-bar {
  position: absolute;
  top: 14px;
  right: 20px;
  z-index: 10;
  background: transparent !important;
  border: none !important;
  padding: 0 !important;
  margin: 0 !important;
  width: auto !important;
}

/* 毛玻璃气泡主体 */
.kb-bubble {
  display: inline-flex;
  align-items: center;
  gap: 6px;                           /* 图标与文字间距 */
  padding: 6px 14px;
  border-radius: 20px;                /* 全圆角胶囊感 */
  
  /* 深色半透明与高模糊滤镜 */
  background: rgba(30, 31, 35, 0.65);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  
  /* 极细微光边框 */
  border: 1px solid var(--primary-color);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
  
  /* 字体与颜色 */
  color: #ffffff;                     /* 高亮荧光黄/绿 */
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.3px;
  user-select: none;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

/* 鼠标悬停交互效果 */
.kb-bubble:hover {
  background: rgba(76, 80, 95, 0.85);
  border-color: rgb(211, 248, 2); /* 边框泛微光 */
  transform: translateY(-2px);           /* 微微向上悬浮 */
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.35);
}

</style>

