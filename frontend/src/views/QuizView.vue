<template>
  <div class="quiz-page">
    <h2 class="page-title">AI 出题助手</h2>

    <div class="quiz-card">
      <div class="quiz-toolbar">
        <el-select v-model="subject" class="subject-select" placeholder="随机学科" style="width: 200px">
          <el-option label="随机学科" value="" />
          <el-option v-for="s in subjects" :key="s" :label="s" :value="s" />
        </el-select>
        <el-button class="theme-btn" :loading="loading" @click="generate">
          {{ current ? '换一题' : '生成题目' }}
        </el-button>
      </div>

      <el-divider />

      <div v-if="current" class="question-area">
        <div class="q-meta">
          <el-tag size="small">{{ current.subject }}</el-tag>
          <el-tag v-if="current.knowledge_point" size="small" type="info" class="kp-tag">
            {{ current.knowledge_point }}
          </el-tag>
        </div>

        <p class="q-text">{{ current.question }}</p>

        <el-radio-group v-model="selected" class="option-group" :disabled="submitted">
          <el-radio
            v-for="opt in current.options"
            :key="opt"
            :value="opt[0]"
            class="option-item"
            border
          >
            {{ opt }}
          </el-radio>
        </el-radio-group>

        <div class="actions">
          <el-button
            class="theme-btn"
            :disabled="!selected || submitted"
            :loading="checking"
            @click="submit"
          >
            提交答案
          </el-button>
        </div>

        <div v-if="result" class="result-box" :class="result.correct ? 'ok' : 'bad'">
          <div class="result-line">
            <el-tag :type="result.correct ? 'success' : 'danger'" size="large">
              {{ result.correct ? '✓ 回答正确' : '✗ 回答错误' }}
            </el-tag>
            <span class="answer-text">正确答案：{{ result.answer }}</span>
          </div>
          <p v-if="result.analysis" class="analysis">{{ result.analysis }}</p>
          <p v-else class="analysis muted">（暂无解析）</p>
        </div>
      </div>

      <div v-else class="empty-tip">
        <p>点击「生成题目」，从 408 题库中随机抽一道选择题。</p>
        <p class="muted">答案取自题库；操作系统缺答案的题由本地模型判定。</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

const subjects = ['数据结构', '操作系统', '组成原理', '计算机网络']
const subject = ref('')
const loading = ref(false)
const checking = ref(false)
const current = ref(null)
const selected = ref('')
const submitted = ref(false)
const result = ref(null)

async function generate() {
  loading.value = true
  try {
    const r = await fetch('/api/quiz/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ subject: subject.value || null })
    })
    const data = await r.json()
    if (!r.ok) throw new Error(data.detail || '生成失败')
    current.value = data
    selected.value = ''
    submitted.value = false
    result.value = null
  } catch (e) {
    ElMessage.error('生成题目失败：' + e.message)
  } finally {
    loading.value = false
  }
}

async function submit() {
  if (!selected.value || !current.value) return
  checking.value = true
  try {
    const r = await fetch('/api/quiz/check', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question_id: current.value.question_id,
        user_answer: selected.value
      })
    })
    const data = await r.json()
    if (!r.ok) throw new Error(data.detail || '提交失败')
    result.value = data
    submitted.value = true
  } catch (e) {
    ElMessage.error('提交失败：' + e.message)
  } finally {
    checking.value = false
  }
}
</script>

<style scoped>
.quiz-page {
  height: 100%;
  overflow-y: auto;
  padding: 24px 28px;
  background-color: #131417;
  color: #e5e7eb;
}

.page-title {
  margin: 0 0 18px;
  font-size: 22px;
  font-weight: 700;
}

.quiz-card {
  max-width: 860px;
  background-color: #1b1c21;
  border: 1px solid #2a2b31;
  border-radius: 12px;
  padding: 22px 24px;
}

.quiz-toolbar {
  display: flex;
  align-items: center;
  gap: 14px;
}

.question-area {
  animation: fade-in 0.25s ease;
}

@keyframes fade-in {
  from { opacity: 0; transform: translateY(6px); }
  to   { opacity: 1; transform: translateY(0); }
}

.q-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
}

.kp-tag {
  max-width: 420px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.q-text {
  font-size: 17px;
  line-height: 1.7;
  margin: 0 0 18px;
  color: #f0f1f5;
}

.option-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
}

.option-item {
  width: 100%;
  margin-right: 0;
  height: auto;
  padding: 12px 16px;
  white-space: normal;
  line-height: 1.5;
}

.actions {
  margin-top: 20px;
}

.theme-btn {
  background-color: var(--primary-color) !important;
  border-color: var(--primary-color) !important;
  color: #000000 !important;
  font-weight: 600;
}

.theme-btn:hover:not(.is-disabled) {
  filter: brightness(0.92);
}

.theme-btn.is-disabled {
  background-color: #2a2b31 !important;
  border-color: #2a2b31 !important;
  color: #6b7280 !important;
  filter: none;
}

.result-box {
  margin-top: 20px;
  padding: 14px 16px;
  border-radius: 10px;
  border: 1px solid transparent;
}

.result-box.ok {
  background-color: rgba(52, 211, 153, 0.10);
  border-color: rgba(52, 211, 153, 0.35);
}

.result-box.bad {
  background-color: rgba(248, 113, 113, 0.10);
  border-color: rgba(248, 113, 113, 0.35);
}

.result-line {
  display: flex;
  align-items: center;
  gap: 14px;
}

.answer-text {
  font-size: 15px;
  font-weight: 600;
}

.analysis {
  margin: 12px 0 0;
  font-size: 14px;
  line-height: 1.7;
}

.empty-tip {
  color: #b8bcc8;
  font-size: 15px;
  text-align: center;
  padding: 40px 0 28px;
}

.muted {
  color: #8e8ea0;
  font-size: 13px;
}
</style>
