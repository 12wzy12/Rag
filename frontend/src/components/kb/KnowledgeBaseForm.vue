<script setup lang="ts">
import { reactive, ref } from 'vue'

import { useKbStore } from '@/stores/kb'
import { getErrorMessage } from '@/api/client'

const store = useKbStore()

const open = ref(false)
const saving = ref(false)
const error = ref<string | null>(null)
const form = reactive({ name: '', description: '' })

async function submit() {
  const name = form.name.trim()
  if (!name) {
    error.value = '请填写知识库名称'
    return
  }
  saving.value = true
  error.value = null
  try {
    await store.create({ name, description: form.description.trim() })
    open.value = false
    form.name = ''
    form.description = ''
  } catch (err) {
    error.value = getErrorMessage(err)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="kb-form">
    <button v-if="!open" class="btn primary" @click="open = true">＋ 新建知识库</button>

    <form v-else class="form" @submit.prevent="submit">
      <input
        v-model="form.name"
        class="field"
        placeholder="知识库名称（必填）"
        maxlength="200"
        autofocus
      />
      <input
        v-model="form.description"
        class="field"
        placeholder="简介（选填）"
        maxlength="500"
      />
      <div class="actions">
        <button type="button" class="btn" :disabled="saving" @click="open = false">取消</button>
        <button type="submit" class="btn primary" :disabled="saving">
          {{ saving ? '创建中…' : '创建' }}
        </button>
      </div>
      <p v-if="error" class="error">{{ error }}</p>
    </form>
  </div>
</template>

<style scoped>
.kb-form {
  display: flex;
  flex-direction: column;
}

.form {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  align-items: center;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 14px 16px;
}

.field {
  flex: 1;
  min-width: 200px;
  padding: 9px 12px;
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-sm);
  font-size: 13px;
  background: var(--surface);
}

.field:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-weak);
}

.actions {
  display: flex;
  gap: 8px;
}

.btn {
  padding: 8px 16px;
  border: 1px solid var(--border-strong);
  background: var(--surface);
  border-radius: var(--radius-sm);
  font-size: 13px;
  color: var(--text);
}

.btn:hover:not(:disabled) {
  background: var(--surface-2);
}

.btn.primary {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
  font-weight: 600;
}

.btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.error {
  margin: 4px 0 0;
  color: var(--danger);
  font-size: 12px;
  flex-basis: 100%;
}
</style>
