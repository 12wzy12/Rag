<script setup lang="ts">
import { useKbStore } from '@/stores/kb'

withDefaults(defineProps<{ label?: string }>(), { label: '知识库' })

const store = useKbStore()
</script>

<template>
  <div class="kb-selector">
    <span class="label">{{ label }}</span>
    <select
      :value="store.currentKbId ?? ''"
      class="select"
      @change="store.select(Number(($event.target as HTMLSelectElement).value))"
    >
      <option value="" disabled>请先选择知识库</option>
      <option v-for="kb in store.items" :key="kb.id" :value="kb.id">
        {{ kb.name }}（{{ kb.document_count }} 文档）
      </option>
    </select>
  </div>
</template>

<style scoped>
.kb-selector {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.label {
  color: var(--text-secondary);
  font-size: 13px;
  white-space: nowrap;
}

.select {
  min-width: 220px;
  padding: 8px 10px;
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-sm);
  background: var(--surface);
  font-size: 13px;
  color: var(--text);
}

.select:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-weak);
}
</style>
