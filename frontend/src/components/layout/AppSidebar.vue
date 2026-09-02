<script setup lang="ts">
import { useRoute } from 'vue-router'

const route = useRoute()

const nav = [
  { path: '/knowledge-bases', label: '知识库管理', icon: '📚' },
  { path: '/documents', label: '文档上传', icon: '📄' },
  { path: '/search', label: '语义检索', icon: '🔍' },
  { path: '/chat', label: '智能问答', icon: '💬' },
]

function isActive(path: string): boolean {
  return route.path === path
}
</script>

<template>
  <aside class="sidebar">
    <div class="brand">
      <span class="brand-mark">RAG</span>
      <span class="brand-text">智能知识库</span>
    </div>
    <nav class="nav">
      <router-link
        v-for="item in nav"
        :key="item.path"
        :to="item.path"
        class="nav-item"
        :class="{ active: isActive(item.path) }"
      >
        <span class="nav-icon">{{ item.icon }}</span>
        <span>{{ item.label }}</span>
      </router-link>
    </nav>
  </aside>
</template>

<style scoped>
.sidebar {
  width: var(--sidebar-width);
  flex-shrink: 0;
  background: var(--surface);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  padding: 20px 14px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 10px 20px;
}

.brand-mark {
  background: var(--accent);
  color: #fff;
  font-weight: 700;
  font-size: 13px;
  padding: 4px 8px;
  border-radius: var(--radius-sm);
  letter-spacing: 0.4px;
}

.brand-text {
  font-weight: 650;
  font-size: 15px;
}

.nav {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 12px;
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  font-size: 14px;
  transition: background 0.15s, color 0.15s;
}

.nav-item:hover {
  background: var(--surface-2);
  color: var(--text);
}

.nav-item.active {
  background: var(--accent-weak);
  color: var(--accent);
  font-weight: 600;
}

.nav-icon {
  font-size: 15px;
}
</style>
