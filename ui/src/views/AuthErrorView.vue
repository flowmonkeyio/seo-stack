<script setup lang="ts">
// AuthErrorView — shown when bootstrap or any subsequent /api/v1/* call
// returns 401, or when the daemon is unreachable.

import { computed } from 'vue'
import { storeToRefs } from 'pinia'

import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const { state } = storeToRefs(authStore)

const errorMessage = computed<string>(() => {
  if (state.value.kind === 'error') {
    return state.value.message
  }
  return 'Authentication required.'
})

const errorStatus = computed<number | null>(() => {
  if (state.value.kind === 'error' && typeof state.value.status === 'number') {
    return state.value.status
  }
  return null
})

async function retry(): Promise<void> {
  await authStore.bootstrap()
  if (authStore.ready) {
    window.location.assign('/projects')
  }
}
</script>

<template>
  <div class="mx-auto flex min-h-[60vh] max-w-xl flex-col items-center justify-center text-center">
    <h1 class="text-2xl font-bold tracking-tight">
      Daemon unreachable
    </h1>
    <p class="mt-3 text-sm text-gray-600 dark:text-gray-400">
      {{ errorMessage }}
      <span v-if="errorStatus !== null"> (HTTP {{ errorStatus }})</span>
    </p>
    <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">
      Make sure the content-stack daemon is running on
      <code class="font-mono">127.0.0.1:5180</code>. Try
      <code class="font-mono">make serve</code> from the repo root.
    </p>
    <button
      type="button"
      class="mt-6 rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-500"
      @click="retry"
    >
      Retry
    </button>
  </div>
</template>
