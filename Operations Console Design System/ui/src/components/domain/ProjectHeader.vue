<script setup lang="ts">
import UiBadge from '../ui/UiBadge.vue'
import UiButton from '../ui/UiButton.vue'

defineProps<{
  name: string
  slug?: string
  description?: string
  state?: 'active' | 'paused' | 'archived' | 'draft'
}>()

defineEmits<{ (e: 'edit'): void; (e: 'archive'): void }>()

const stateTone = {
  active: 'success',
  paused: 'warning',
  archived: 'neutral',
  draft: 'info',
} as const
</script>

<template>
  <header class="flex flex-wrap items-start gap-4 border-b border-border-subtle pb-4">
    <div class="flex-1 min-w-0">
      <div class="flex items-center gap-2">
        <h1 class="text-xl font-semibold text-fg-strong truncate">{{ name }}</h1>
        <UiBadge v-if="state" :tone="stateTone[state]">{{ state }}</UiBadge>
      </div>
      <p v-if="slug" class="font-mono text-xs text-fg-muted mt-0.5">{{ slug }}</p>
      <p v-if="description" class="text-sm text-fg-muted mt-1 max-w-prose">{{ description }}</p>
    </div>
    <div class="flex gap-2">
      <slot name="actions">
        <UiButton variant="secondary" size="sm" @click="$emit('edit')">Edit</UiButton>
        <UiButton variant="ghost" size="sm" @click="$emit('archive')">Archive</UiButton>
      </slot>
    </div>
  </header>
</template>
