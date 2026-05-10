<!--
  UiIconButton — square button for single-icon actions.
  Always requires `aria-label`. Wraps UiButton with iconOnly enforced.
-->
<script setup lang="ts">
import UiButton from './UiButton.vue';

defineProps<{
  ariaLabel: string;
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  disabled?: boolean;
  loading?: boolean;
  href?: string;
  type?: 'button' | 'submit' | 'reset';
}>();

defineEmits<{ (e: 'click', ev: MouseEvent): void }>();
</script>

<template>
  <UiButton
    icon-only
    :aria-label="ariaLabel"
    :variant="variant ?? 'ghost'"
    :size="size"
    :disabled="disabled"
    :loading="loading"
    :href="href"
    :type="type"
    @click="(ev) => $emit('click', ev)"
  >
    <slot />
  </UiButton>
</template>
