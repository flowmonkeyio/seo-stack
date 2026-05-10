<!--
  UiDescriptionItem — single term/value row inside <UiDescriptionList>.
  Allows rich slot content for the value.
-->
<script setup lang="ts">
defineProps<{
  label: string;
  hint?: string;
  mono?: boolean;
  numeric?: boolean;
}>();
</script>

<template>
  <div class="grid grid-cols-[max-content_1fr] items-baseline gap-3 py-1.5 border-b border-subtle last:border-b-0">
    <dt class="text-xs font-medium uppercase tracking-wider text-fg-subtle min-w-[8rem]">
      {{ label }}
      <p v-if="hint" class="text-2xs font-normal normal-case tracking-normal text-fg-disabled mt-0.5">{{ hint }}</p>
    </dt>
    <dd :class="[
      'text-sm text-fg-default min-w-0 break-words',
      mono && 'font-mono text-xs',
      numeric && 'text-right tabular-nums',
    ]">
      <slot />
    </dd>
  </div>
</template>
