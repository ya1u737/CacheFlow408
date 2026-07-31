<template>
  <div class="status-container">
    <el-card class="status-card" shadow="hover">
      <!-- 头部 -->
      <template #header>
        <div class="card-header">
          <div class="header-title">
            <span class="icon">📊</span>
            <span>模型运行状态</span>
          </div>
          <!-- 🔥 纯文字无 emoji 的刷新按钮 -->
          <span 
            class="refresh-text" 
            :class="{ 'is-loading': loading }" 
            @click="!loading && fetchStatus()"
          >
            {{ loading ? '刷新中...' : '刷新状态' }}
          </span>
        </div>
      </template>

      <!-- 骨架屏 / 内容区 -->
      <el-skeleton :loading="loading" animated :rows="5">
        <template #default>
          <div class="status-grid">
            <!-- 运行状态 -->
            <div class="status-item">
              <span class="label">运行状态</span>
              <span class="value">
                <span class="status-dot" :class="isOnline ? 'online' : 'offline'"></span>
                <span class="status-text">{{ status.status || '未知' }}</span>
              </span>
            </div>

            <!-- 当前模式 -->
            <div class="status-item">
              <span class="label">当前模式</span>
              <span class="value">
                <span class="mode-tag">{{ status.mode || '默认' }}</span>
              </span>
            </div>

            <!-- LLM 模型 -->
            <div class="status-item">
              <span class="label">LLM 模型</span>
              <span class="value code-font">{{ status.model || '未加载' }}</span>
            </div>

            <!-- Embedding 模型 -->
            <div class="status-item">
              <span class="label">Embedding 模型</span>
              <span class="value code-font">{{ status.embedding || '未加载' }}</span>
            </div>

            <!-- 知识库状态 -->
            <div class="status-item">
              <span class="label">知识库状态</span>
              <span class="value">
                <span :class="['knowledge-badge', status.has_knowledge ? 'has-data' : 'empty-data']">
                  {{ status.has_knowledge ? '● 已加载' : '○ 未加载' }}
                </span>
              </span>
            </div>
          </div>
        </template>
      </el-skeleton>
    </el-card>
  </div>
</template>

<script>
export default {
  data() {
    return { 
      status: {}, 
      loading: true 
    }
  },
  computed: {
    isOnline() {
      const s = (this.status.status || '').toLowerCase()
      return s === 'running' || s === 'normal' || s === 'ok' || s === '正常'
    }
  },
  mounted() { 
    this.fetchStatus() 
  },
  methods: {
    async fetchStatus() {
      this.loading = true
      try {
        const r = await fetch('/api/status')
        this.status = await r.json()
      } catch (err) {
        console.error('获取状态失败:', err)
      } finally {
        this.loading = false
      }
    }
  }
}
</script>

<style scoped>
.status-container {
  max-width: 650px;
  margin: 30px auto;
  padding: 0 16px;
}

/* 深色卡片主体 */
:deep(.el-card) {
  background-color: #1e1f23 !important;
  border: 1px solid #2e3035 !important;
  border-radius: 12px;
  color: #ececec;
}

:deep(.el-card__header) {
  border-bottom: 1px solid #2a2b30 !important;
  padding: 16px 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: #f3f4f6;
}

.status-grid {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* 深灰底色列表条目 */
.status-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background-color: #18191c;
  border: 1px solid rgba(255, 255, 255, 0.03);
  border-radius: 8px;
  transition: background-color 0.2s;
}

.status-item:hover {
  background-color: #222328;
}

.label {
  font-size: 14px;
  color: #9ca3af;
  font-weight: 500;
}

.value {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: #f3f4f6;
}

/* 等宽字体高亮模型 */
.code-font {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.1);
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 13px;
  color: #c8e338; /* 搭配系统的荧光黄绿 */
}

/* 模式 Tag */
.mode-tag {
  background-color: rgba(59, 130, 246, 0.15);
  color: #60a5fa;
  border: 1px solid rgba(59, 130, 246, 0.3);
  padding: 2px 10px;
  border-radius: 20px;
  font-size: 12px;
}

/* 知识库状态 Badge */
.knowledge-badge {
  font-size: 12px;
  padding: 3px 10px;
  border-radius: 20px;
}

.knowledge-badge.has-data {
  background-color: rgba(16, 185, 129, 0.15);
  color: #34d399;
  border: 1px solid rgba(16, 185, 129, 0.3);
}

.knowledge-badge.empty-data {
  background-color: rgba(156, 163, 175, 0.15);
  color: #9ca3af;
  border: 1px solid rgba(156, 163, 175, 0.3);
}

/* 在线/离线发光小圆点 */
.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}

.status-dot.online {
  background-color: #10b981;
  box-shadow: 0 0 8px #10b981;
}

.status-dot.offline {
  background-color: #ef4444;
  box-shadow: 0 0 8px #ef4444;
}

/* 刷新按钮：实心荧光绿圆角矩形 + 黑色文字 */
.refresh-text {
  background-color: #c8e338;   /* 👈 实心荧光绿背景 */
  color: #000000;              /* 👈 黑色文字 */
  font-size: 12px;
  font-weight: 700;            /* 文字加粗 */
  padding: 4px 12px;
  border-radius: 6px;          /* 圆角矩形 */
  cursor: pointer;
  user-select: none;
  transition: all 0.2s ease;
  display: inline-block;
}

/* 悬停时加亮并提升透明度/发光 */
.refresh-text:hover {
  background-color: #d8f348;   /* 悬停稍微提亮 */
  box-shadow: 0 0 10px rgba(200, 227, 56, 0.4); /* 荧光发光效果 */
}

/* 刷新/加载中状态 */
.refresh-text.is-loading {
  background-color: #374151;   /* 变深灰背景 */
  color: #9ca3af;              /* 灰字 */
  cursor: not-allowed;
  box-shadow: none;
}


</style>