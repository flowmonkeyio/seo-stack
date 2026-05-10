<script setup lang="ts">
import { ref } from 'vue'

import StatusBadge from '../StatusBadge.vue'
import UiButton from '../ui/UiButton.vue'

defineProps<{
  criterionId: string
  label: string
  category: string
  verdict?: 'pass' | 'partial' | 'fail' | string
  notes?: string | null
  required?: boolean
}>()

defineEmits<{
  (e: 'edit'): void
}>()

const open = ref(false)
</script>

<template>
  <div class="rounded-md border border-default bg-bg-surface">
    <button
      type="button"
      class="focus-ring-inset flex w-full items-center justify-between gap-3 px-3 py-2 text-left hover:bg-bg-surface-alt"
      :aria-expanded="open"
      @click="open = !open"
    >
      <span class="min-w-0">
        <span class="block truncate text-sm font-medium text-fg-strong">{{ label }}</span>
        <span class="font-mono text-xs text-fg-muted">{{ criterionId }} · {{ category }}</span>
      </span>
      <StatusBadge
        domain="eeat"
        :status="verdict ?? 'unevaluated'"
      />
    </button>
    <div
      v-if="open"
      class="border-t border-subtle p-3"
    >
      <p class="text-sm text-fg-muted">
        {{ notes ?? 'No evaluation notes yet.' }}
      </p>
      <div class="mt-3 flex items-center justify-between">
        <span class="text-xs text-fg-muted">{{ required ? 'Core requirement' : 'Optional criterion' }}</span>
        <UiButton
          size="sm"
          variant="secondary"
          @click="$emit('edit')"
        >
          Edit criterion
        </UiButton>
      </div>
    </div>
  </div>
</template>
