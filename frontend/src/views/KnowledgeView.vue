<template>
  <div class="knowledge-container">
    <!-- 1. 顶部 Header 区 -->
    <div class="page-header">
      <div class="header-title">
        <span class="icon">📚</span>
        <h3>知识库管理</h3>
      </div>
      <el-popconfirm
        title="确定要清空当前所有知识库数据吗？"
        confirm-button-text="确认清空"
        cancel-button-text="取消"
        confirm-button-type="danger"
        @confirm="clearKnowledge"
      >
        <template #reference>
          <el-button type="danger" plain class="clear-btn">
            <span class="btn-icon">🗑️</span> 清空知识库
          </el-button>
        </template>
      </el-popconfirm>
    </div>

    <!-- 2. 核心区：分左右/上下两列结构 -->
    <div class="knowledge-grid">
      <!-- 左侧/上方：文件上传区 -->
      <div class="section-card upload-section">
        <div class="card-title">文件导入</div>
        <el-upload
          class="custom-drag-upload"
          action="/api/upload"
          :before-upload="startFakeProgress"
          :on-success="onUploadSuccess"
          :on-error="onUploadError"
          :accept="'.pdf,.txt,.docx,.md'"
          drag
          multiple
        >
          <div class="upload-inner">
            <div class="upload-icon-box">
              <span class="upload-emoji">📤</span>
            </div>
            <div class="upload-text">
              <span class="primary-text">拖拽文件到此处，或 <em>点击上传</em></span>
              <span class="sub-text">支持 文本型PDF、TXT、DOCX、Markdown </span>
            </div>
          </div>
        </el-upload>

        <div v-if="uploadProgress > 0" class="upload-progress">
          <el-progress
            :percentage="uploadProgress"
            :status="progressStatus"
            :stroke-width="14"
          >
            <span v-if="uploadProgress < 100" class="progress-text">📄 正在解析文档... {{ uploadProgress }}%</span>
            <span v-else-if="progressStatus === 'success'" class="progress-text">✅ 解析完成</span>
          </el-progress>
        </div>
      </div>

      <!-- 右侧/下方：预设 408 核心知识库卡片 -->
      <div class="section-card preset-section">
        <div class="card-title">预设学科知识库 </div>
        <div class="preset-grid">
          <div
            v-for="(filename, label) in presetDocs"
            :key="label"
            class="preset-card"
            :class="{ 'is-loading': loadingPresets[filename] }"
            @click="loadPreset(filename)"
          >
            <div class="preset-icon">📖</div>
            <div class="preset-info">
              <div class="preset-name">{{ label.replace('_', ' ') }}</div>
              <div class="preset-sub">{{ filename }}</div>
            </div>
            <el-button 
              size="small" 
              class="preset-btn" 
              :loading="loadingPresets[filename]"
            >
              {{ loadingPresets[filename] ? '加载中' : '加载' }}
            </el-button>
          </div>
        </div>
      </div>
    </div>

    <!-- 3. 底部：知识库实时状态看板 -->
    <div class="section-card status-section">
      <div class="card-title-bar">
        <div class="card-title">系统知识库状态</div>
        <el-button size="small" class="refresh-btn" @click="fetchStatus" :loading="isRefreshing">
          刷新状态
        </el-button>
      </div>

      <!-- 状态解析卡片网格 -->
      <div class="status-metrics" v-if="parsedStatus">
        <div class="metric-card">
          <div class="metric-label">向量索引状态</div>
          <div class="metric-value highlight">{{ parsedStatus.status || parsedStatus.state || 'Active' }}</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">已加载文档数</div>
          <div class="metric-value">{{ parsedStatus.document_count ?? parsedStatus.doc_count ?? 0 }}</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">分块切片 (Chunks)</div>
          <div class="metric-value">{{ parsedStatus.chunk_count ?? parsedStatus.total_chunks ?? 0 }}</div>
        </div>
      </div>

      <!-- 兜底/原始 JSON 调试折叠面板 -->
      <el-collapse class="json-collapse">
        <el-collapse-item title="查看原始 JSON 状态响应" name="1">
          <pre class="raw-json">{{ statusText }}</pre>
        </el-collapse-item>
      </el-collapse>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'

// 预设文档列表
const presetDocs = ref({
  '数据结构_知识点': '数据结构_知识点.md',
  '操作系统_知识点': '操作系统_知识点.md',
  '计算机网络_知识点': '计算机网络_知识点.md',
  '组成原理_知识点': '组成原理_知识点.md',
})

const statusText = ref('')
const loadingPresets = ref({})
const isRefreshing = ref(false)

// ===== 假进度条 =====
const uploadProgress = ref(0)
const progressStatus = ref('')
let progressTimer = null

// 随机进度生成器（每次上传体验都不同）
const startFakeProgress = () => {
  uploadProgress.value = 1
  progressStatus.value = ''

  // 随机初始速度 1~5
  let speed = Math.floor(Math.random() * 4) + 1

  // 随机目标区间：70~92，每次都不一样
  const maxTarget = Math.floor(Math.random() * 22) + 70

  clearInterval(progressTimer)
  progressTimer = setInterval(() => {
    // 随机增量每次 1~5
    const inc = Math.floor(Math.random() * 5) + 1
    let next = uploadProgress.value + inc

    // 在接近目标时减速（避免跳变）
    if (next >= maxTarget) {
      // 随机停在目标区间内浮动，不再往上
      uploadProgress.value = maxTarget + Math.floor(Math.random() * 5) - 2
    } else {
      uploadProgress.value = next
    }

    // 防止超过 99
    if (uploadProgress.value >= 99) uploadProgress.value = 95 + Math.floor(Math.random() * 4)
  }, speed * 120) // 间隔时间也随机
}

// 解析 statusText 为对象，方便看板渲染
const parsedStatus = computed(() => {
  try {
    return JSON.parse(statusText.value)
  } catch {
    return null
  }
})

// 获取系统状态
const fetchStatus = async () => {
  isRefreshing.value = true
  try {
    const r = await fetch('/api/status')
    const data = await r.json()
    statusText.value = JSON.stringify(data, null, 2)
  } catch {
    ElMessage.error('无法连接到服务端获取状态')
  } finally {
    isRefreshing.value = false
  }
}

// 转换并加载预设知识库
const loadPreset = async (filename) => {
  if (loadingPresets.value[filename]) return
  loadingPresets.value[filename] = true

  try {
    const r = await fetch(`/api/load_knowledge?filename=${encodeURIComponent(filename)}`, { method: 'POST' })
    const d = await r.json()
    if (d.status === 'ok' || r.ok) {
      ElMessage.success(`《${filename}》加载成功！`)
      fetchStatus()
    } else {
      ElMessage.error(d.message || '加载失败')
    }
  } catch {
    ElMessage.error('请求发送失败，请检查后端接口')
  } finally {
    loadingPresets.value[filename] = false
  }
}

// 清空知识库
const clearKnowledge = async () => {
  try {
    const r = await fetch('/api/clear', { method: 'DELETE' })
    const d = await r.json()
    ElMessage.success(d.message || '知识库已成功清空')
    fetchStatus()
  } catch {
    ElMessage.error('清空操作失败')
  }
}

// 上传回调
const onUploadSuccess = (response, file, fileList) => {
  if (response.status === 'ok') {
    // 真正成功：进度条直接跳到 100
    clearInterval(progressTimer)
    uploadProgress.value = 100
    progressStatus.value = 'success'
    ElMessage.success(`${response.source} 上传成功，共生成 ${response.chunks} 个知识片段`)
  } else {
    // 业务失败（HTTP 200 但 status=error）
    ElMessage.error(`上传失败：${response.message || '未知错误'}`)
    // 手动移除失败文件，避免显示对钩
    const idx = fileList.findIndex(f => f.uid === file.uid)
    if (idx !== -1) fileList.splice(idx, 1)
  }
  fetchStatus()
}

const onUploadError = (err, file, fileList) => {
  const msg = err?.response?.data?.message || '文件上传失败，请检查格式和内容'
  ElMessage.error(`上传失败：${msg}`)
  // 失败：清除进度条
  clearInterval(progressTimer)
  uploadProgress.value = 0
  // 从列表移除失败文件
  const idx = fileList.findIndex(f => f.uid === file.uid)
  if (idx !== -1) fileList.splice(idx, 1)
}

onMounted(() => {
  fetchStatus()
})
</script>

<style scoped>
.knowledge-container {
  max-width: 1000px;
  margin: 0 auto;
  padding: 24px;
  color: #ececec;
  height: 100%;
  box-sizing: border-box;
  overflow-y: auto;
}

/* 顶部标题栏 */
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-title .icon {
  font-size: 24px;
}

.header-title h3 {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  color: #f3f4f6;
}

.clear-btn {
  border-radius: 8px;
  font-weight: 600;
}

/* 网格两列布局 */
.knowledge-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-bottom: 20px;
}

@media (max-width: 768px) {
  .knowledge-grid {
    grid-template-columns: 1fr;
  }
}

/* 基础卡片风格 */
.section-card {
  background-color: #18191c;
  border: 1px solid #28292d;
  border-radius: 12px;
  padding: 20px;
}

.card-title {
  font-size: 15px;
  font-weight: 700;
  color: #e5e7eb;
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.card-title .badge {
  font-size: 11px;
  background-color: rgba(200, 227, 56, 0.15);
  color: #c8e338;
  border: 1px solid rgba(200, 227, 56, 0.3);
  padding: 1px 6px;
  border-radius: 4px;
}

/* 自定义拖拽上传区域 */
.custom-drag-upload :deep(.el-upload-dragger) {
  background-color: #131417 !important;
  border: 2px dashed #33353b !important;
  border-radius: 10px !important;
  padding: 30px 16px !important;
  transition: all 0.25s ease;
}

.custom-drag-upload :deep(.el-upload-dragger:hover) {
  border-color: #c8e338 !important;
  background-color: rgba(200, 227, 56, 0.02) !important;
}

.upload-inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.upload-icon-box {
  width: 48px;
  height: 48px;
  background-color: #202227;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
}

.upload-text {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.primary-text {
  font-size: 14px;
  color: #9ca3af;
}

.primary-text em {
  color: #c8e338;
  font-style: normal;
  font-weight: 600;
}

.sub-text {
  font-size: 12px;
  color: #6b7280;
}

/* 假进度条样式 */
.upload-progress {
  margin-top: 16px;
}

.upload-progress :deep(.el-progress-bar__outer) {
  background-color: #26272c;
}

.progress-text {
  font-size: 12px;
  color: #9ca3af;
}

/* 预设知识库卡片 */
.preset-grid {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.preset-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background-color: #131417;
  border: 1px solid #232428;
  padding: 12px 14px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.preset-card:hover {
  border-color: #c8e338;
  transform: translateY(-1px);
}

.preset-icon {
  font-size: 20px;
  margin-right: 12px;
}

.preset-info {
  flex: 1;
}

.preset-name {
  font-size: 14px;
  font-weight: 600;
  color: #f3f4f6;
}

.preset-sub {
  font-size: 12px;
  color: #6b7280;
  font-family: monospace;
}

.preset-btn {
  background-color: rgba(255, 255, 255, 0.05) !important;
  border-color: rgba(255, 255, 255, 0.1) !important;
  color: #e5e7eb !important;
  border-radius: 6px;
}

.preset-card:hover .preset-btn {
  background-color: #c8e338 !important;
  border-color: #c8e338 !important;
  color: #000000 !important;
  font-weight: 700;
}

/* 状态看板区域 */
.status-section {
  margin-top: 10px;
}

.card-title-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

/* 刷新按钮：实心荧光绿圆角矩形 + 黑色文字 */
:deep(.refresh-btn) {
  background-color: #c8e338 !important;   /* 实心荧光绿 */
  border: none !important;                /* 去掉原本的细边框 */
  color: #000000 !important;              /* 纯黑文字 */
  font-weight: 700 !important;            /* 文字加粗 */
  border-radius: 6px !important;          /* 圆角矩形 */
  padding: 6px 14px !important;
  font-size: 12px !important;
  transition: all 0.2s ease !important;
}

/* 悬停时提亮并加发光效果 */
:deep(.refresh-btn:hover) {
  background-color: #d8f348 !important;
  box-shadow: 0 0 10px rgba(200, 227, 56, 0.4) !important;
  color: #000000 !important;
}

/* 加载状态/禁用状态 */
:deep(.refresh-btn.is-loading),
:deep(.refresh-btn.is-disabled) {
  background-color: #374151 !important;
  color: #9ca3af !important;
  border: none !important;
}
.status-metrics {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-top: 12px;
  margin-bottom: 16px;
}

.metric-card {
  background-color: #131417;
  border: 1px solid #232428;
  padding: 14px;
  border-radius: 8px;
}

.metric-label {
  font-size: 12px;
  color: #8e8ea0;
  margin-bottom: 6px;
}

.metric-value {
  font-size: 20px;
  font-weight: 700;
  color: #ffffff;
  font-family: monospace;
}

.metric-value.highlight {
  color: #c8e338;
}

/* 折叠面板与 JSON 降级显示 */
.json-collapse :deep(.el-collapse),
.json-collapse :deep(.el-collapse-item__header),
.json-collapse :deep(.el-collapse-item__wrap) {
  background-color: transparent !important;
  border: none !important;
  color: #6b7280 !important;
  font-size: 12px;
}

.raw-json {
  background-color: #111214;
  padding: 12px;
  border-radius: 6px;
  color: #22c55e;
  font-family: monospace;
  font-size: 12px;
  margin: 0;
  max-height: 150px;
  overflow-y: auto;
}
</style>