<!--
  UiJsonBlock — formatted, syntax-highlighted JSON.
  Accepts an object/array (will JSON.stringify with indent) OR a raw string.
-->
<script setup lang="ts">
import { computed } from 'vue';
import UiCodeBlock from './UiCodeBlock.vue';

const props = withDefaults(defineProps<{
  data: unknown;
  indent?: number;
  numbered?: boolean;
  wrap?: boolean;
  copyable?: boolean;
  maxHeight?: string;
  density?: 'compact' | 'comfortable';
  ariaLabel?: string;
}>(), {
  indent: 2,
  copyable: true,
});

const code = computed(() => {
  if (typeof props.data === 'string') return props.data;
  try {
    return JSON.stringify(props.data, null, props.indent);
  } catch (e) {
    return String(props.data);
  }
});
</script>

<template>
  <UiCodeBlock
    :code="code"
    language="json"
    :numbered="numbered"
    :wrap="wrap"
    :copyable="copyable"
    :max-height="maxHeight"
    :density="density"
    :aria-label="ariaLabel"
  />
</template>
