<template>
  <div style="max-width: 600px; margin: 0 auto">
    <h3>📊 模型状态</h3>
    <el-skeleton :loading="loading" animated>
      <template #default>
        <el-descriptions :column="1" border>
          <el-descriptions-item label="运行状态">{{ status.status }}</el-descriptions-item>
          <el-descriptions-item label="当前模式">{{ status.mode }}</el-descriptions-item>
          <el-descriptions-item label="LLM 模型">{{ status.model }}</el-descriptions-item>
          <el-descriptions-item label="Embedding 模型">{{ status.embedding }}</el-descriptions-item>
          <el-descriptions-item label="知识库状态">
            <el-tag :type="status.has_knowledge ? 'success' : 'info'">
              {{ status.has_knowledge ? '已加载' : '空' }}
            </el-tag>
          </el-descriptions-item>
        </el-descriptions>
        <el-button @click="fetchStatus" style="margin-top: 16px" size="small">🔄 刷新</el-button>
      </template>
    </el-skeleton>
  </div>
</template>

<script>
export default {
  data() {
    return { status: {}, loading: true }
  },
  mounted() { this.fetchStatus() },
  methods: {
    async fetchStatus() {
      this.loading = true
      const r = await fetch('/api/status')
      this.status = await r.json()
      this.loading = false
    }
  }
}
</script>