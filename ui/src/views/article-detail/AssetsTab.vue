<script setup lang="ts">
// AssetsTab — gallery of `article_assets` rows.
//
// Wires to:
// - `GET /api/v1/articles/{id}/assets`
// - `POST /api/v1/articles/{id}/assets`
// - `PATCH /api/v1/articles/{id}/assets/{asset_id}`
// - `DELETE /api/v1/articles/{id}/assets/{asset_id}`

import { onMounted, ref, watch } from 'vue'

import { apiFetch, apiWrite, ApiError } from '@/lib/client'
import { useToastsStore } from '@/stores/toasts'
import { ArticleAssetKind, type components } from '@/api'

type Asset = components['schemas']['ArticleAssetOut']
type AssetCreateRequest = components['schemas']['AssetCreateRequest']

const props = defineProps<{
  articleId: number
}>()

const toasts = useToastsStore()

const assets = ref<Asset[]>([])
const loading = ref(false)
const showCreate = ref(false)
const submitting = ref(false)

interface NewAsset {
  kind: `${ArticleAssetKind}`
  url: string
  alt_text: string
  width: number | null
  height: number | null
  prompt: string
}

const draft = ref<NewAsset>(emptyDraft())

function emptyDraft(): NewAsset {
  return { kind: 'inline', url: '', alt_text: '', width: null, height: null, prompt: '' }
}

const KIND_OPTIONS = Object.values(ArticleAssetKind)

async function load(): Promise<void> {
  loading.value = true
  try {
    const rows = await apiFetch<Asset[]>(`/api/v1/articles/${props.articleId}/assets`)
    assets.value = rows
  } catch (err) {
    toasts.error('Failed to load assets', err instanceof Error ? err.message : undefined)
  } finally {
    loading.value = false
  }
}

function openCreate(): void {
  draft.value = emptyDraft()
  showCreate.value = true
}

function closeCreate(): void {
  if (submitting.value) return
  showCreate.value = false
}

async function submitCreate(): Promise<void> {
  if (submitting.value) return
  if (!draft.value.url.trim()) {
    toasts.error('Missing URL', 'Asset URL is required.')
    return
  }
  submitting.value = true
  try {
    const body: AssetCreateRequest = {
      kind: draft.value.kind as ArticleAssetKind,
      url: draft.value.url.trim(),
      alt_text: draft.value.alt_text.trim() || null,
      width: draft.value.width,
      height: draft.value.height,
      prompt: draft.value.prompt.trim() || null,
    }
    await apiWrite<Asset>(`/api/v1/articles/${props.articleId}/assets`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
    })
    toasts.success('Asset added')
    showCreate.value = false
    await load()
  } catch (err) {
    toasts.error('Failed to add asset', err instanceof Error ? err.message : undefined)
  } finally {
    submitting.value = false
  }
}

async function removeAsset(asset: Asset): Promise<void> {
  try {
    await apiFetch(`/api/v1/articles/${props.articleId}/assets/${asset.id}`, {
      method: 'DELETE',
    })
    toasts.success('Asset removed')
    assets.value = assets.value.filter((a) => a.id !== asset.id)
  } catch (err) {
    if (err instanceof ApiError) {
      toasts.error('Delete failed', err.message)
    } else {
      toasts.error('Delete failed', err instanceof Error ? err.message : undefined)
    }
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

onMounted(load)
watch(() => props.articleId, load)
</script>

<template>
  <section
    class="space-y-4"
    aria-labelledby="cs-assets-tab-title"
  >
    <div class="flex flex-wrap items-baseline justify-between gap-2">
      <h2
        id="cs-assets-tab-title"
        class="text-base font-semibold"
      >
        Assets
      </h2>
      <button
        type="button"
        class="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
        @click="openCreate"
      >
        Add asset
      </button>
    </div>

    <p
      v-if="loading"
      class="text-sm text-gray-500"
    >
      Loading…
    </p>

    <p
      v-else-if="assets.length === 0"
      class="rounded border border-dashed border-gray-300 p-4 text-sm text-gray-600 dark:border-gray-700 dark:text-gray-300"
    >
      No assets yet. Add a hero image, inline figure, OG card, or other media.
    </p>

    <ul
      v-else
      class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3"
    >
      <li
        v-for="asset in assets"
        :key="asset.id"
        class="rounded border border-gray-200 bg-white p-3 shadow-sm dark:border-gray-800 dark:bg-gray-900"
      >
        <div class="mb-2 flex items-center justify-between gap-2">
          <span
            class="rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-800 dark:bg-blue-900/40 dark:text-blue-300"
          >
            {{ asset.kind }}
          </span>
          <button
            type="button"
            class="rounded border border-red-300 px-2 py-0.5 text-xs text-red-700 hover:bg-red-50 dark:border-red-700 dark:text-red-300 dark:hover:bg-red-900/30"
            @click="removeAsset(asset)"
          >
            Remove
          </button>
        </div>
        <img
          v-if="IMAGE_KINDS.has(asset.kind) && asset.url"
          :src="asset.url"
          :alt="asset.alt_text ?? ''"
          class="mb-2 h-32 w-full rounded object-cover"
        >
        <p class="break-words font-mono text-xs text-gray-700 dark:text-gray-300">
          {{ asset.url }}
        </p>
        <p
          v-if="asset.alt_text"
          class="mt-1 text-xs text-gray-600 dark:text-gray-400"
        >
          alt: {{ asset.alt_text }}
        </p>
        <p
          v-if="asset.width && asset.height"
          class="mt-1 text-xs text-gray-500 dark:text-gray-400"
        >
          {{ asset.width }}×{{ asset.height }}
        </p>
      </li>
    </ul>

    <div
      v-if="showCreate"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="cs-asset-add-title"
      @click.self="closeCreate"
    >
      <div
        class="w-full max-w-md rounded-lg border border-gray-200 bg-white p-5 shadow-xl dark:border-gray-700 dark:bg-gray-900"
      >
        <h3
          id="cs-asset-add-title"
          class="mb-3 text-lg font-semibold"
        >
          Add asset
        </h3>
        <form
          class="space-y-3"
          @submit.prevent="submitCreate"
        >
          <label class="block text-sm">
            <span class="font-medium">Kind</span>
            <select
              v-model="draft.kind"
              class="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-800"
            >
              <option
                v-for="k in KIND_OPTIONS"
                :key="k"
                :value="k"
              >
                {{ k }}
              </option>
            </select>
          </label>
          <label class="block text-sm">
            <span class="font-medium">URL</span>
            <input
              v-model="draft.url"
              type="url"
              required
              class="mt-1 w-full rounded border border-gray-300 px-2 py-1 font-mono text-xs dark:border-gray-700 dark:bg-gray-800"
            >
          </label>
          <label class="block text-sm">
            <span class="font-medium">Alt text</span>
            <input
              v-model="draft.alt_text"
              type="text"
              class="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-800"
            >
          </label>
          <div class="grid grid-cols-2 gap-3">
            <label class="block text-sm">
              <span class="font-medium">Width</span>
              <input
                v-model.number="draft.width"
                type="number"
                min="0"
                class="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-800"
              >
            </label>
            <label class="block text-sm">
              <span class="font-medium">Height</span>
              <input
                v-model.number="draft.height"
                type="number"
                min="0"
                class="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-800"
              >
            </label>
          </div>
          <label class="block text-sm">
            <span class="font-medium">Prompt</span>
            <input
              v-model="draft.prompt"
              type="text"
              class="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-800"
            >
          </label>
          <div class="mt-3 flex justify-end gap-2">
            <button
              type="button"
              class="rounded border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-100 dark:border-gray-700 dark:hover:bg-gray-800"
              :disabled="submitting"
              @click="closeCreate"
            >
              Cancel
            </button>
            <button
              type="submit"
              class="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
              :disabled="submitting"
            >
              {{ submitting ? 'Saving…' : 'Add asset' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </section>
</template>
