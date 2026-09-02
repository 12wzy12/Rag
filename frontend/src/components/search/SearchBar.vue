<script setup lang="ts">
import { ref } from 'vue'

import { useSearchStore } from '@/stores/search'

const store = useSearchStore()

const draft = ref('')

function submit() {
  const keyword = draft.value.trim()
  if (!keyword || store.loading) return
  store.run(keyword)
}
</script>

<template>
  <form class="search-bar" @submit.prevent="submit">
    <input
      v-model="draft"
      type="search"
      class="search-input"
      placeholder="输入问题，检索知识库…"
      autocomplete="off"
    />
    <div class="topk">
      <label for="topk">Top K</label>
      <select id="topk" v-model.number="store.topK" :disabled="store.loading">
        <option :value="3">3</option>
        <option :value="5">5</option>
        <option :value="8">8</option>
        <option :value="10">10</option>
      </select>
    </div>
    <button class="btn primary" type="submit" :disabled="store.loading">
      {{ store.loading ? '检索中…' : '检索' }}
    </button>
  </form>
</template>

<style scoped>
.search-bar {
  display: flex;
  align-items: center;
  gap: 12px;
}

.search-input {
  flex: 1;
  padding: 12px 16px;
  border: 1px solid var(--border-strong);
  border-radius: var(--radius);
  font-size: 14px;
  background: var(--surface);
  transition: border-color 0.15s, box-shadow 0.15s;
}

.search-input:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-weak);
}

.topk {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-secondary);
  font-size: 13px;
}

.topk select {
  padding: 9px 10px;
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-sm);
  background: var(--surface);
  font-size: 13px;
}

.btn {
  padding: 11px 22px;
  border: none;
  border-radius: var(--radius);
  font-size: 14px;
  font-weight: 600;
  color: #fff;
  background: var(--accent);
  transition: background 0.15s;
  white-space: nowrap;
}

.btn:hover:not(:disabled) {
  background: var(--accent-strong);
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
