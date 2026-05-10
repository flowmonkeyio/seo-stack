<script setup lang="ts">
import UiButton from '../ui/UiButton.vue'

defineProps<{
  dirty?: boolean
  saving?: boolean
  canPublish?: boolean
  canRefresh?: boolean
  disabled?: boolean
}>()

defineEmits<{
  (e: 'save'): void
  (e: 'publish'): void
  (e: 'refresh'): void
  (e: 'discard'): void
}>()
</script>

<template>
  <div class="sticky bottom-0 z-sticky border-t border-default bg-bg-surface/95 px-4 py-3 shadow-sm">
    <div class="mx-auto flex max-w-content-wide flex-wrap items-center justify-between gap-3">
      <p class="text-sm text-fg-muted">
        <span
          v-if="dirty"
          class="text-warning-fg"
        >Unsaved changes</span>
        <span
          v-else
          class="text-success-fg"
        >Article is saved</span>
      </p>
      <div class="flex items-center gap-2">
        <UiButton
          variant="ghost"
          size="sm"
          :disabled="disabled || saving || !dirty"
          @click="$emit('discard')"
        >
          Discard
        </UiButton>
        <UiButton
          variant="secondary"
          size="sm"
          :disabled="disabled || saving || !canRefresh"
          @click="$emit('refresh')"
        >
          Mark refresh
        </UiButton>
        <UiButton
          variant="secondary"
          size="sm"
          :loading="saving"
          :disabled="disabled || !dirty"
          @click="$emit('save')"
        >
          Save
        </UiButton>
        <UiButton
          variant="primary"
          size="sm"
          :disabled="disabled || saving || !canPublish"
          @click="$emit('publish')"
        >
          Publish
        </UiButton>
      </div>
    </div>
  </div>
</template>
