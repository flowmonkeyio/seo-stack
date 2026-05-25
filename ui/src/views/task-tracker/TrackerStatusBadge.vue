<script setup lang="ts">
import { computed } from 'vue'

import { UiBadge } from '@/components/ui'
import type { TrackerStatus } from '@/lib/task-tracker/types'

const props = defineProps<{
  status: TrackerStatus | string
}>()

const tone = computed(() => {
  switch (props.status) {
    case 'complete':
      return 'success'
    case 'in-progress':
      return 'info'
    case 'deferred':
      return 'warning'
    default:
      return 'neutral'
  }
})

const label = computed(() => props.status.replace(/-/g, ' '))
</script>

<template>
  <UiBadge
    :tone="tone"
    variant="subtle"
    size="sm"
    :dot="status === 'in-progress'"
    :pulse="status === 'in-progress'"
  >
    {{ label }}
  </UiBadge>
</template>
