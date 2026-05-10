<script setup lang="ts">
import UiBadge from '../ui/UiBadge.vue'
import UiButton from '../ui/UiButton.vue'
import UiCard from '../ui/UiCard.vue'

defineProps<{
  kind: string
  url?: string | null
  altText?: string | null
  width?: number | null
  height?: number | null
  bytes?: number | null
  selected?: boolean
}>()

defineEmits<{
  (e: 'edit'): void
  (e: 'remove'): void
  (e: 'select'): void
}>()

function formatBytes(bytes?: number | null) {
  if (!bytes) return 'Unknown size'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}
</script>

<template>
  <UiCard
    density="compact"
    :variant="selected ? 'default' : 'subtle'"
  >
    <div class="aspect-video overflow-hidden rounded-sm border border-subtle bg-bg-sunken">
      <img
        v-if="url"
        :src="url"
        :alt="altText ?? ''"
        class="h-full w-full object-cover"
      >
      <div
        v-else
        class="flex h-full items-center justify-center text-xs text-fg-muted"
      >
        No preview
      </div>
    </div>
    <div class="mt-3 space-y-2">
      <div class="flex items-center justify-between gap-2">
        <UiBadge tone="info">
          {{ kind }}
        </UiBadge>
        <span class="font-mono text-xs text-fg-muted">
          <template v-if="width && height">{{ width }}x{{ height }}</template>
        </span>
      </div>
      <p class="line-clamp-2 min-h-[2rem] text-sm text-fg-default">
        {{ altText ?? 'Missing alt text' }}
      </p>
      <p class="font-mono text-xs text-fg-muted">
        {{ formatBytes(bytes) }}
      </p>
    </div>
    <template #footer>
      <UiButton
        size="sm"
        variant="ghost"
        @click="$emit('select')"
      >
        Select
      </UiButton>
      <UiButton
        size="sm"
        variant="secondary"
        @click="$emit('edit')"
      >
        Edit
      </UiButton>
      <UiButton
        size="sm"
        variant="danger"
        @click="$emit('remove')"
      >
        Remove
      </UiButton>
    </template>
  </UiCard>
</template>
