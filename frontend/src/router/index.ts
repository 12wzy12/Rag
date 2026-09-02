import { createRouter, createWebHistory } from 'vue-router'

import ChatView from '@/views/ChatView.vue'
import DocumentsView from '@/views/DocumentsView.vue'
import KnowledgeBasesView from '@/views/KnowledgeBasesView.vue'
import SearchView from '@/views/SearchView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', redirect: '/knowledge-bases' },
    {
      path: '/knowledge-bases',
      name: 'knowledge-bases',
      component: KnowledgeBasesView,
      meta: { title: '知识库管理' },
    },
    {
      path: '/documents',
      name: 'documents',
      component: DocumentsView,
      meta: { title: '文档' },
    },
    {
      path: '/search',
      name: 'search',
      component: SearchView,
      meta: { title: '语义检索' },
    },
    {
      path: '/chat',
      name: 'chat',
      component: ChatView,
      meta: { title: '智能问答' },
    },
  ],
})

router.afterEach((to) => {
  const base = 'RAG 智能知识库'
  document.title = to.meta.title ? `${to.meta.title} · ${base}` : base
})

export default router
