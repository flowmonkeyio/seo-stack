<script setup lang="ts">
// PlaceholderView — generic shell for routes that are wired before the
// operator-facing screen is ready.

import {
  UiBadge,
  UiEmptyState,
  UiPageHeader,
  UiPageShell,
} from '@/components/ui'

interface Props {
  title: string
  milestone: string
  description?: string
}

withDefaults(defineProps<Props>(), {
  description: '',
})
</script>

<template>
  <UiPageShell>
    <UiPageHeader
      :title="title"
      :description="description || 'This route is wired, but the operator workflow is not available yet.'"
    >
      <template #titleMeta>
        <UiBadge
          tone="warning"
          variant="subtle"
        >
          unavailable
        </UiBadge>
      </template>
    </UiPageHeader>
    <div class="flex min-h-[40vh] items-center justify-center">
      <UiEmptyState
        title="Workflow unavailable"
        :description="description || 'Use the surrounding project navigation to continue the current workflow.'"
        icon="wrench"
        size="md"
      />
    </div>
  </UiPageShell>
</template>
