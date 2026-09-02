<script setup lang="ts">
import { computed } from 'vue'

import type { DocStatus } from '@/types'

const props = defineProps<{ status: DocStatus }>()

const LABELS: Record<DocStatus, string> = {
  pending: '待解析',
  parsing: '解析中',
  ready: '可用',
  failed: '失败',
}

const cls = computed(() => `badge badge-${props.status}`)
</script>

<template>
  <span :class="cls">{{ LABELS[status] }}</span>
</template>

<style scoped>
.badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}

.badge::before {
  content: '';
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

.badge-ready {
  color: var(--success);
  background: var(--success-weak);
}

.badge-parsing,
.badge-pending {
  color: var(--warning);
  background: var(--warning-weak);
}

.badge-failed {
  color: var(--danger);
  background: var(--danger-weak);
}
</style>
