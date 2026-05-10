<script setup lang="ts">
import UiBadge from '../ui/UiBadge.vue'
import UiButton from '../ui/UiButton.vue'
import UiCard from '../ui/UiCard.vue'

defineProps<{
  query: string
  url?: string | null
  clicks?: number | null
  impressions?: number | null
  ctr?: number | null
  position?: number | null
  opportunity: 'striking-distance' | 'low-ctr' | 'missing-intent' | 'cannibalization' | string
}>()

defineEmits<{
  (e: 'createTopic'): void
  (e: 'inspect'): void
}>()
</script>

<template>
  <UiCard density="compact">
    <template #header>
      <div class="min-w-0">
        <h3 class="truncate text-sm font-semibold text-fg-strong">
          {{ query }}
        </h3>
        <p
          v-if="url"
          class="truncate text-xs text-fg-muted"
        >
          {{ url }}
        </p>
      </div>
      <UiBadge tone="info">
        {{ opportunity }}
      </UiBadge>
    </template>
    <dl class="grid grid-cols-4 gap-3 text-xs">
      <div>
        <dt class="text-fg-muted">
          Clicks
        </dt>
        <dd class="font-mono text-fg-strong">
          {{ clicks ?? 0 }}
        </dd>
      </div>
      <div>
        <dt class="text-fg-muted">
          Impr.
        </dt>
        <dd class="font-mono text-fg-strong">
          {{ impressions ?? 0 }}
        </dd>
      </div>
      <div>
        <dt class="text-fg-muted">
          CTR
        </dt>
        <dd class="font-mono text-fg-strong">
          {{ ctr == null ? 'n/a' : `${(ctr * 100).toFixed(1)}%` }}
        </dd>
      </div>
      <div>
        <dt class="text-fg-muted">
          Pos.
        </dt>
        <dd class="font-mono text-fg-strong">
          {{ position == null ? 'n/a' : position.toFixed(1) }}
        </dd>
      </div>
    </dl>
    <template #footer>
      <UiButton
        size="sm"
        variant="ghost"
        @click="$emit('inspect')"
      >
        Inspect
      </UiButton>
      <UiButton
        size="sm"
        variant="primary"
        @click="$emit('createTopic')"
      >
        Create topic
      </UiButton>
    </template>
  </UiCard>
</template>
