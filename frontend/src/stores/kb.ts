import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import * as api from '@/api/knowledgeBases'
import { getErrorMessage } from '@/api/client'

import type { KnowledgeBase } from '@/types'

const STORAGE_KEY = 'rag.current_kb_id'

export const useKbStore = defineStore('kb', () => {
  const items = ref<KnowledgeBase[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const currentKbId = ref<number | null>(null)

  const currentKb = computed(
    () => items.value.find((kb) => kb.id === currentKbId.value) ?? null,
  )

  async function fetchKnowledgeBases(prefer?: number) {
    loading.value = true
    error.value = null
    try {
      items.value = await api.listKnowledgeBases()
    } catch (err) {
      error.value = getErrorMessage(err)
    } finally {
      loading.value = false
    }
    // 恢复上次选择的库；否则选中第一个。
    const stored = Number(localStorage.getItem(STORAGE_KEY))
    const target =
      prefer ??
      (stored && items.value.some((kb) => kb.id === stored) ? stored : null)
    currentKbId.value =
      target ?? items.value[0]?.id ?? null
    if (currentKbId.value) localStorage.setItem(STORAGE_KEY, String(currentKbId.value))
  }

  async function create(payload: { name: string; description?: string }) {
    const kb = await api.createKnowledgeBase(payload)
    items.value = [kb, ...items.value]
    currentKbId.value = kb.id
    localStorage.setItem(STORAGE_KEY, String(kb.id))
    return kb
  }

  async function remove(id: number) {
    await api.deleteKnowledgeBase(id)
    items.value = items.value.filter((kb) => kb.id !== id)
    if (currentKbId.value === id) {
      currentKbId.value = items.value[0]?.id ?? null
      if (currentKbId.value) localStorage.setItem(STORAGE_KEY, String(currentKbId.value))
      else localStorage.removeItem(STORAGE_KEY)
    }
  }

  function select(id: number) {
    currentKbId.value = id
    localStorage.setItem(STORAGE_KEY, String(id))
  }

  return {
    items,
    loading,
    error,
    currentKbId,
    currentKb,
    fetchKnowledgeBases,
    create,
    remove,
    select,
  }
})
