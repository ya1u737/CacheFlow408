<template>
  <div style="max-width: 600px; margin: 0 auto">
    <h3>📚 知识库管理</h3>

    <el-upload
      :action="`/api/upload`"
      :on-success="onUploadSuccess"
      :on-error="onUploadError"
      drag
      multiple
      style="margin-bottom: 20px"
    >
      <el-icon style="font-size: 48px; color: #409eff">📄</el-icon>
      <div>拖拽文件到此处，或点击上传</div>
      <template #tip><div style="font-size: 12px; color: #888">支持 PDF / TXT / DOCX</div></template>
    </el-upload>

    <el-divider />

    <h4>预设知识库</h4>
    <div v-for="(fn, label) in presetDocs" :key="label" style="margin-bottom: 8px">
      <el-button @click="loadPreset(fn)" size="small">{{ label }}</el-button>
    </div>

    <el-divider />

    <el-button @click="clearKnowledge" type="danger" size="small">🗑️ 清空知识库</el-button>

    <el-divider />

    <h4>知识库状态</h4>
    <pre style="background: #1e1f20; padding: 12px; border-radius: 6px; color: #0f0">{{ statusText }}</pre>
  </div>
</template>

<script>
import { ElMessage } from 'element-plus'
export default {
  data() {
    return {
      presetDocs: {
        '数据结构_知识点': '数据结构_知识点.md',
        '操作系统_知识点': '操作系统_知识点.md',
        '计算机网络_知识点': '计算机网络_知识点.md',
        '组成原理_知识点': '组成原理_知识点.md',
      },
      statusText: ''
    }
  },
  mounted() { this.fetchStatus() },
  methods: {
    async fetchStatus() {
      const r = await fetch('/api/status')
      this.statusText = JSON.stringify(await r.json(), null, 2)
    },
    async loadPreset(filename) {
      const r = await fetch(`/api/load_knowledge?filename=${filename}`, { method: 'POST' })
      const d = await r.json()
      ElMessage(d.status === 'ok' ? { type: 'success', message: `${filename} 已加载` } : { type: 'error', message: d.message })
      this.fetchStatus()
    },
    async clearKnowledge() {
      const r = await fetch('/api/clear', { method: 'DELETE' })
      const d = await r.json()
      ElMessage({ type: 'success', message: d.message })
      this.fetchStatus()
    },
    onUploadSuccess() { ElMessage({ type: 'success', message: '上传成功' }); this.fetchStatus() },
    onUploadError() { ElMessage({ type: 'error', message: '上传失败' }) },
  }
}
</script>