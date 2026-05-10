<script setup lang="ts">
import { ref } from 'vue'

import StatusBadge from '../StatusBadge.vue'
import UiCodeBlock from '../ui/UiCodeBlock.vue'
import UiJsonBlock from '../ui/UiJsonBlock.vue'

export interface RunStepAccordionItem {
  id: string
  label: string
  status: string
  duration?: string | null
  error?: string | null
  output?: unknown
  log?: string | null
}

defineProps<{
  steps: RunStepAccordionItem[]
  initiallyOpen?: string
}>()

const openIds = ref<Set<string>>(new Set())

function toggle(id: string) {
  const next = new Set(openIds.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  openIds.value = next
}

function isOpen(id: string, initiallyOpen?: string) {
  return openIds.value.has(id) || initiallyOpen === id
}
</script>

<template>
  <div class="divide-y divide-border-subtle rounded-md border border-default bg-bg-surface">
    <section
      v-for="step in steps"
      :key="step.id"
    >
      <button
        type="button"
        class="focus-ring-inset flex w-full items-center justify-between gap-3 px-4 py-3 text-left hover:bg-bg-surface-alt"
        :aria-expanded="isOpen(step.id, initiallyOpen)"
        @click="toggle(step.id)"
      >
        <span class="min-w-0">
          <span class="block truncate text-sm font-medium text-fg-strong">{{ step.label }}</span>
          <span class="block font-mono text-xs text-fg-muted">{{ step.id }}</span>
        </span>
        <span class="flex shrink-0 items-center gap-3">
          <span
            v-if="step.duration"
            class="font-mono text-xs text-fg-muted"
          >{{ step.duration }}</span>
          <StatusBadge
            kind="job"
            :status="step.status"
          />
        </span>
      </button>
      <div
        v-if="isOpen(step.id, initiallyOpen)"
        class="space-y-3 border-t border-subtle bg-bg-surface-alt p-4"
      >
        <p
          v-if="step.error"
          class="rounded-sm border border-danger-border bg-danger-subtle p-2 text-sm text-danger-fg"
        >
          {{ step.error }}
        </p>
        <UiJsonBlock
          v-if="step.output !== undefined"
          :data="step.output"
          copyable
        />
        <UiCodeBlock
          v-if="step.log"
          :code="step.log"
          language="log"
          copyable
          wrap
        />
        <slot
          name="step"
          :step="step"
        />
      </div>
    </section>
  </div>
</template>
