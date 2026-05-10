<script setup lang="ts">
import StatusBadge from '../StatusBadge.vue'

defineProps<{
  status: 'healthy' | 'degraded' | 'failing' | 'notConnected' | 'expiring' | 'expired' | string
  label?: string
  size?: 'sm' | 'md'
}>()
</script>

<template>
  <StatusBadge
    domain="integration"
    :status="status"
    :label="label"
    :size="size ?? 'sm'"
  />
</template>
