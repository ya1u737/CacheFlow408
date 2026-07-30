import { createRouter, createWebHashHistory } from 'vue-router'
import ChatView from './views/ChatView.vue'
import KnowledgeView from './views/KnowledgeView.vue'
import StatusView from './views/StatusView.vue'

const routes = [
  { path: '/',             component: ChatView },
  { path: '/knowledge',    component: KnowledgeView },
  { path: '/status',       component: StatusView },
]

export default createRouter({ history: createWebHashHistory(), routes })