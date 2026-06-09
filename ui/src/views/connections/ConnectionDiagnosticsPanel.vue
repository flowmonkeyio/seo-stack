<script setup lang="ts">
import { UiJsonBlock, UiSectionHeader } from '@/components/ui'
import { sanitizeForDisplay } from '@/lib/stackos/json'

defineProps<{
  authStatus: unknown
}>()
</script>

<template>
  <section
    v-if="authStatus"
    aria-label="Connection diagnostics"
  >
    <UiSectionHeader
      title="Diagnostics"
      description="Sanitized daemon-side auth status for support and verification."
      as="h3"
    />
    <UiJsonBlock
      :data="sanitizeForDisplay(authStatus)"
      density="compact"
      max-height="34rem"
      wrap
      aria-label="Sanitized auth status"
    />
  </section>
</template>
