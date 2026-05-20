<script setup lang="ts">
// AssetsTab — read-only gallery of `article_assets` rows.

import { onMounted, ref, watch } from 'vue'

import { apiFetch, formatApiError } from '@/lib/client'
import { useToastsStore } from '@/stores/toasts'
import type { components } from '@/api'

type Asset = components['schemas']['ArticleAssetOut']

const props = defineProps<{
  articleId: number
}>()

const toasts = useToastsStore()

const assets = ref<Asset[]>([])
const loading = ref(false)
const brokenAssetIds = ref<Set<number>>(new Set())

async function load(): Promise<void> {
  loading.value = true
  try {
    const rows = await apiFetch<Asset[]>(`/api/v1/articles/${props.articleId}/assets`)
    assets.value = rows
  } catch (err) {
    toasts.error('Failed to load assets', formatApiError(err))
  } finally {
    loading.value = false
  }
}

const IMAGE_KINDS: Set<string> = new Set([
  'hero',
  'inline',
  'thumbnail',
  'og',
  'twitter',
  'infographic',
  'screenshot',
  'gallery',
])

function markAssetBroken(id: number): void {
  brokenAssetIds.value = new Set([...brokenAssetIds.value, id])
}

function canPreview(asset: Asset): boolean {
  return (
    IMAGE_KINDS.has(asset.kind) &&
    !!asset.url &&
    isPreviewableUrl(asset.url) &&
    !brokenAssetIds.value.has(asset.id)
  )
}

function isPreviewableUrl(value: string): boolean {
  try {
    const parsed = new URL(value, globalThis.location?.origin ?? 'http://localhost')
    return (
      parsed.protocol === 'data:' ||
      parsed.protocol === 'blob:' ||
      parsed.origin === globalThis.location?.origin ||
      !parsed.hostname.endsWith('.local')
    )
  } catch {
    return false
  }
}

onMounted(load)
watch(() => props.articleId, load)
</script>

<template>
  <section
    class="space-y-4"
    aria-labelledby="cs-assets-tab-title"
  >
    <div>
      <h2
        id="cs-assets-tab-title"
        class="text-base font-semibold"
      >
        Assets
      </h2>
    </div>

    <p
      v-if="loading"
      class="text-sm text-fg-muted"
    >
      Loading…
    </p>

    <p
      v-else-if="assets.length === 0"
      class="rounded-md border border-dashed border-default bg-bg-surface p-4 text-sm text-fg-muted"
    >
      No assets yet.
    </p>

    <ul
      v-else
      class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3"
    >
      <li
        v-for="asset in assets"
        :key="asset.id"
        class="rounded-md border border-subtle bg-bg-surface p-3 shadow-xs"
      >
        <div class="mb-2 flex items-center justify-between gap-2">
          <span
            class="rounded-full border border-accent bg-accent-subtle px-2 py-0.5 text-xs font-medium text-accent-fg"
          >
            {{ asset.kind }}
          </span>
        </div>
        <div class="mb-3 flex h-36 w-full items-center justify-center overflow-hidden rounded-sm border border-subtle bg-bg-surface-alt">
          <img
            v-if="canPreview(asset)"
            :src="asset.url"
            :alt="asset.alt_text ?? ''"
            class="h-full w-full object-cover"
            @error="markAssetBroken(asset.id)"
          >
          <div
            v-else
            class="px-4 text-center text-xs text-fg-muted"
          >
            Preview unavailable
          </div>
        </div>
        <p class="break-words font-mono text-xs text-fg-muted">
          {{ asset.url }}
        </p>
        <p
          v-if="asset.alt_text"
          class="mt-1 text-xs text-fg-muted"
        >
          alt: {{ asset.alt_text }}
        </p>
        <p
          v-if="asset.width && asset.height"
          class="mt-1 text-xs text-fg-subtle"
        >
          {{ asset.width }}x{{ asset.height }}
        </p>
      </li>
    </ul>
  </section>
</template>
