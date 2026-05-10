<script setup lang="ts">
import UiBadge from '../ui/UiBadge.vue'
import UiButton from '../ui/UiButton.vue'

export interface SourceLedgerItem {
  id: string | number
  title: string
  url?: string | null
  publisher?: string | null
  cited?: boolean
  notes?: string | null
}

defineProps<{
  items: SourceLedgerItem[]
}>()

defineEmits<{
  (e: 'open', item: SourceLedgerItem): void
}>()
</script>

<template>
  <div class="divide-y divide-border-subtle rounded-md border border-default bg-bg-surface">
    <div
      v-for="item in items"
      :key="item.id"
      class="flex items-start justify-between gap-3 px-4 py-3"
    >
      <div class="min-w-0">
        <div class="flex flex-wrap items-center gap-2">
          <h3 class="truncate text-sm font-medium text-fg-strong">
            {{ item.title }}
          </h3>
          <UiBadge
            :tone="item.cited ? 'success' : 'neutral'"
            size="sm"
          >
            {{ item.cited ? 'Cited' : 'Unused' }}
          </UiBadge>
        </div>
        <p class="mt-1 truncate text-xs text-fg-muted">
          <span v-if="item.publisher">{{ item.publisher }} · </span>{{ item.url ?? 'No URL' }}
        </p>
        <p
          v-if="item.notes"
          class="mt-2 text-sm text-fg-muted"
        >
          {{ item.notes }}
        </p>
      </div>
      <UiButton
        size="sm"
        variant="ghost"
        @click="$emit('open', item)"
      >
        Open
      </UiButton>
    </div>
  </div>
</template>
