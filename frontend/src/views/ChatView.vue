<template>
  <div style="max-width: 800px; margin: 0 auto">
    <div style="height: 60vh; overflow-y: auto; margin-bottom: 20px">
      <div v-for="(msg, i) in messages" :key="i">
        <div v-if="msg.role === 'user'" style="text-align: right; margin: 10px 0">
          <el-tag type="primary">🧑 你</el-tag>
          <p style="color: #fff; margin: 4px 0">{{ msg.content }}</p>
        </div>
        <div v-else style="margin: 10px 0">
          <el-tag type="success">🤖 AI</el-tag>
          <p style="color: #e3e3e3; margin: 4px 0; white-space: pre-wrap">{{ msg.content }}</p>
          <div v-if="msg.references && msg.references.length">
            <el-collapse>
              <el-collapse-item title="📚 检索知识点" name="refs">
                <div v-for="(ref, j) in msg.references" :key="j" style="margin-bottom: 8px">
                  <p style="margin: 0; color: #aaa">
                    📌 {{ j + 1 }}. {{ ref.preview.slice(0, 15) }}{{ ref.preview.length > 15 ? '...' : '' }}
                  </p>
                  <p style="margin: 0; font-size: 12px; color: #888">📄 {{ ref.source }} P{{ ref.page }}</p>
                </div>
              </el-collapse-item>
            </el-collapse>
          </div>
          <p v-if="msg.perf" style="font-size: 12px; color: #666; margin: 2px 0">
            检索 {{ msg.perf.retrieval }}s | 生成 {{ msg.perf.generation }}s | 总计 {{ msg.perf.total }}s
          </p>
        </div>
      </div>
      <div v-if="loading" style="color: #888">⏳ 思考中...</div>
    </div>
    <el-input
      v-model="question"
      placeholder="在此提问 ..."
      @keyup.enter="sendQuestion"
      :disabled="loading"
      size="large"
    >
      <template #append>
        <el-button @click="sendQuestion" :disabled="loading" type="primary">发送</el-button>
      </template>
    </el-input>
  </div>
</template>

<script>
import axios from 'axios'

export default {
  data() {
    return { question: '', messages: [], loading: false }
  },
  methods: {
    async sendQuestion() {
      if (!this.question.trim()) return
      const q = this.question
      this.question = ''
      this.messages.push({ role: 'user', content: q })
      this.loading = true

      const msgIndex = this.messages.length
      this.messages.push({ role: 'assistant', content: '', references: [], perf: null })

      const t0 = Date.now()
      try {
        const resp = await fetch('/api/query_stream', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            question: q,
            chat_history: this.messages.slice(0, -1).map(m => ({ role: m.role, content: m.content })),
            mode: 'ollama'
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
              } else if (msg.type === 'references') {
                this.messages[msgIndex].references = msg.data
              } else if (msg.type === 'done') {
                const total = (Date.now() - t0) / 1000
                this.messages[msgIndex].perf = { retrieval: 0, generation: total, total }
              }
            }
          }
        }
      } catch (e) {
        this.messages[msgIndex].content = '❌ 请求失败: ' + e.message
      }
      this.loading = false
    }
  }
}
</script>