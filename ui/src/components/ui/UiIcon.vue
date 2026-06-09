<script setup lang="ts">
import { computed } from 'vue'

import { iconComponent } from './icons'

const props = defineProps<{
  name?: string
  ariaLabel?: string
}>()

const icon = computed(() => iconComponent(props.name))
</script>

<template>
  <component
    :is="icon"
    v-if="icon"
    class="ui-icon"
    :aria-hidden="ariaLabel ? undefined : 'true'"
    :aria-label="ariaLabel"
    :role="ariaLabel ? 'img' : undefined"
  />
</template>

<style>
/* Zero-specificity default so sizing utilities (h-4 w-4 …) can override. */
:where(.ui-icon) {
  width: 1em;
  height: 1em;
  flex: none;
}
</style>
