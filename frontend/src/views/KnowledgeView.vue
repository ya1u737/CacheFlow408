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

const presetDocs = ref({
  '数据结构_知识点': '数据结构_知识点.md',
  '操作系统_知识点': '操作系统_知识点.md',
  '计算机网络_知识点': '计算机网络_知识点.md',
  '组成原理_知识点': '组成原理_知识点.md',
})

const statusText = ref('')
const loadingPresets = ref({})
const isRefreshing = ref(false)

const uploadProgress = ref(0)
const progressStatus = ref('')
let progressTimer = null

const startFakeProgress = () => {
  uploadProgress.value = 1
  progressStatus.value = ''
  let speed = Math.floor(Math.random() * 4) + 1
  const maxTarget = Math.floor(Math.random() * 22) + 70
  clearInterval(progressTimer)
  progressTimer = setInterval(() => {
    const inc = Math.floor(Math.random() * 5) + 1
    let next = uploadProgress.value + inc
    if (next >= maxTarget) {
      uploadProgress.value = maxTarget + Math.floor(Math.random() * 5) - 2
    } else {
      uploadProgress.value = next
    }
    if (uploadProgress.value >= 99) uploadProgress.value = 95 + Math.floor(Math.random() * 4)
  }, speed * 120)
}

const parsedStatus = computed(() => {
  try {
    return JSON.parse(statusText.value)
  } catch {
    return null
  }
})

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

const onUploadSuccess = (response, file, fileList) => {
  if (response.status === 'ok') {
    clearInterval(progressTimer)
    uploadProgress.value = 100
    progressStatus.value = 'success'
    ElMessage.success(`${response.source} 上传成功，共生成 ${response.chunks} 个知识片段`)
  } else {
    ElMessage.error(`上传失败：${response.message || '未知错误'}`)
    const idx = fileList.findIndex(f => f.uid === file.uid)
    if (idx !== -1) fileList.splice(idx, 1)
  }
  fetchStatus()
}

const onUploadError = (err, file, fileList) => {
  const msg = err?.response?.data?.message || '文件上传失败，请检查格式和内容'
  ElMessage.error(`上传失败：${msg}`)
  clearInterval(progressTimer)
  uploadProgress.value = 0
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
  background-color: color-mix(in srgb, var(--primary-color) 15%, transparent);
  color: var(--primary-color);
  border: 1px solid color-mix(in srgb, var(--primary-color) 30%, transparent);
  padding: 1px 6px;
  border-radius: 4px;
}

.custom-drag-upload :deep(.el-upload-dragger) {
  background-color: #131417 !important;
  border: 2px dashed #33353b !important;
  border-radius: 10px !important;
  padding: 30px 16px !important;
  transition: all 0.25s ease;
}

.custom-drag-upload :deep(.el-upload-dragger:hover) {
  border-color: var(--primary-color) !important;
  background-color: color-mix(in srgb, var(--primary-color) 2%, transparent) !important;
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
  color: var(--primary-color);
  font-style: normal;
  font-weight: 600;
}

.sub-text {
  font-size: 12px;
  color: #6b7280;
}

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
  border-color: var(--primary-color);
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
  background-color: var(--primary-color) !important;
  border-color: var(--primary-color) !important;
  color: #000000 !important;
  font-weight: 700;
}

.status-section {
  margin-top: 10px;
}

.card-title-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

:deep(.refresh-btn) {
  background-color: var(--primary-color) !important;
  border: none !important;
  color: #000000 !important;
  font-weight: 700 !important;
  border-radius: 6px !important;
  padding: 6px 14px !important;
  font-size: 12px !important;
  transition: all 0.2s ease !important;
}

:deep(.refresh-btn:hover) {
  background-color: color-mix(in srgb, var(--primary-color) 80%, white) !important;
  box-shadow: 0 0 10px color-mix(in srgb, var(--primary-color) 40%, transparent) !important;
  color: #000000 !important;
}

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
  color: var(--primary-color);
}

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