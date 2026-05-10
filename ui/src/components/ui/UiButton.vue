<!--
  UiButton — primary action element.

  Variants:
    - primary    : main CTA, filled accent
    - secondary  : default action, outlined
    - ghost      : low-emphasis, no border
    - danger     : destructive
    - link       : inline, underlined

  Sizes: sm | md | lg
  States: default, hover, active, focus-visible, disabled, loading
-->
<script setup lang="ts">
import { computed } from 'vue';

export interface UiButtonProps {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger' | 'link';
  size?: 'sm' | 'md' | 'lg';
  /** Render as <a> when set; otherwise <button>. */
  href?: string;
  type?: 'button' | 'submit' | 'reset';
  disabled?: boolean;
  loading?: boolean;
  /** Stretch to fill parent width. */
  block?: boolean;
  /** Lucide icon name for leading icon (rendered by parent). */
  iconLeft?: string;
  iconRight?: string;
  /** When true and only an icon child is provided, becomes square. Use UiIconButton instead when possible. */
  iconOnly?: boolean;
  /** Aria label — required when iconOnly. */
  ariaLabel?: string;
}

const props = withDefaults(defineProps<UiButtonProps>(), {
  variant: 'secondary',
  size: 'md',
  href: undefined,
  type: 'button',
  disabled: false,
  loading: false,
  block: false,
  iconLeft: undefined,
  iconRight: undefined,
  iconOnly: false,
  ariaLabel: undefined,
});

defineEmits<{
  (e: 'click', ev: MouseEvent): void;
}>();

const isDisabled = computed(() => props.disabled || props.loading);

const variantClass = computed(() => ({
  primary:
    'bg-accent text-fg-on-accent border border-accent hover:bg-accent-hover active:bg-accent-active disabled:bg-fg-disabled disabled:border-fg-disabled disabled:text-fg-inverse',
  secondary:
    'bg-bg-surface text-fg-default border border-default hover:bg-bg-surface-alt hover:border-strong active:bg-bg-sunken disabled:bg-bg-surface disabled:text-fg-disabled',
  ghost:
    'bg-transparent text-fg-default border border-transparent hover:bg-bg-surface-alt active:bg-bg-sunken disabled:text-fg-disabled',
  danger:
    'bg-danger text-fg-on-accent border border-danger hover:bg-danger/90 active:bg-danger/80 disabled:bg-fg-disabled disabled:border-fg-disabled',
  link:
    'bg-transparent text-fg-link border border-transparent hover:underline underline-offset-2 px-0 py-0 h-auto disabled:text-fg-disabled',
}[props.variant]));

const sizeClass = computed(() => ({
  sm: props.iconOnly ? 'h-7 w-7 px-0 text-sm'  : 'h-7 px-2.5 gap-1.5 text-sm',
  md: props.iconOnly ? 'h-8 w-8 px-0 text-sm'  : 'h-8 px-3 gap-2 text-sm',
  lg: props.iconOnly ? 'h-10 w-10 px-0 text-base' : 'h-10 px-4 gap-2 text-base',
}[props.size]));
</script>

<template>
  <component
    :is="href ? 'a' : 'button'"
    :href="href"
    :type="href ? undefined : type"
    :disabled="!href && isDisabled"
    :aria-disabled="isDisabled || undefined"
    :aria-busy="loading || undefined"
    :aria-label="ariaLabel"
    :class="[
      'ui-button focus-ring inline-flex items-center justify-center font-medium rounded-sm transition-colors duration-fast ease-standard select-none whitespace-nowrap',
      variantClass,
      sizeClass,
      block && 'w-full',
      isDisabled && 'cursor-not-allowed',
      loading && 'relative',
    ]"
    @click="(ev: MouseEvent) => !isDisabled && $emit('click', ev)"
  >
    <span
      v-if="loading"
      class="ui-button__spinner"
      aria-hidden="true"
    >
      <svg
        class="animate-spin"
        width="14"
        height="14"
        viewBox="0 0 24 24"
        fill="none"
      >
        <circle
          cx="12"
          cy="12"
          r="9"
          stroke="currentColor"
          stroke-opacity="0.25"
          stroke-width="3"
        />
        <path
          d="M21 12a9 9 0 0 0-9-9"
          stroke="currentColor"
          stroke-width="3"
          stroke-linecap="round"
        />
      </svg>
    </span>
    <slot
      v-else
      name="iconLeft"
    >
      <span
        v-if="iconLeft"
        :class="['i-lucide-' + iconLeft]"
        aria-hidden="true"
      />
    </slot>
    <span
      v-if="!iconOnly"
      class="ui-button__label"
    >
      <slot />
    </span>
    <slot
      v-if="!iconOnly"
      name="iconRight"
    >
      <span
        v-if="iconRight"
        :class="['i-lucide-' + iconRight]"
        aria-hidden="true"
      />
    </slot>
    <span
      v-if="iconOnly && !loading"
      class="ui-button__icon"
    >
      <slot />
    </span>
  </component>
</template>

<style scoped>
.ui-button { line-height: 1; }
.ui-button__spinner { display: inline-flex; }
</style>
