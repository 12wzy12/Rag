import { defineStore } from 'pinia'
import { ref } from 'vue'

import * as api from '@/api/search'
import { getErrorMessage } from '@/api/client'

import type { SearchResult } from '@/types'

export const useSearchStore = defineStore('search', () => {
  const query = ref('')
  const topK = ref(8)
  const result = ref<SearchResult | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  /** 是否已执行过至少一次检索（区分空态与“无结果”）。 */
  const searched = ref(false)

  async function run(kbId: number, q?: string) {
    const keyword = (q ?? query.value).trim()
    if (!keyword) return
    query.value = keyword
    loading.value = true
    error.value = null
    try {
      result.value = await api.searchDocuments(kbId, {
        query: keyword,
        topK: topK.value,
      })
      searched.value = true
    } catch (err) {
      error.value = getErrorMessage(err)
    } finally {
      loading.value = false
    }
  }

  function reset() {
    query.value = ''
    result.value = null
    searched.value = false
    error.value = null
  }

  return { query, topK, result, loading, error, searched, run, reset }
})
