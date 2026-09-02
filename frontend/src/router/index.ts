import { createRouter, createWebHistory } from 'vue-router'

import DocumentsView from '@/views/DocumentsView.vue'
import SearchView from '@/views/SearchView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', redirect: '/documents' },
    {
      path: '/documents',
      name: 'documents',
      component: DocumentsView,
      meta: { title: '知识库' },
    },
    {
      path: '/search',
      name: 'search',
      component: SearchView,
      meta: { title: '检索' },
    },
  ],
})

router.afterEach((to) => {
  const base = 'RAG 知识库'
  document.title = to.meta.title ? `${to.meta.title} · ${base}` : base
})

export default router
