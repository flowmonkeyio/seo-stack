<script setup lang="ts">
// IntegrationsTab — guided vendor setup. The database still stores a
// `kind`, but the UI presents vendors, use cases, and required fields.

import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { apiFetch, apiWrite, ApiError } from '@/lib/client'
import { useToastsStore } from '@/stores/toasts'
import type { components } from '@/api'

type Cred = components['schemas']['IntegrationCredentialOut']
type VendorKind =
  | 'dataforseo'
  | 'firecrawl'
  | 'gsc'
  | 'openai-images'
  | 'reddit'
  | 'jina'
  | 'ahrefs'
  | 'google-paa'

interface FieldSpec {
  key: string
  label: string
  type?: 'text' | 'password'
  placeholder?: string
  help?: string
  required?: boolean
}

interface VendorSpec {
  kind: VendorKind
  name: string
  category: string
  summary: string
  usedBy: string
  setup: 'manual' | 'oauth' | 'none'
  fields?: FieldSpec[]
  dependsOn?: VendorKind[]
  optional?: boolean
  docsHref?: string
}

interface TestResult {
  ok?: boolean
  status?: string
  detail?: string
  message?: string
  [key: string]: unknown
}

const route = useRoute()
const toasts = useToastsStore()

const projectId = computed<number>(() => Number.parseInt(route.params.id as string, 10))

const vendors: VendorSpec[] = [
  {
    kind: 'dataforseo',
    name: 'DataForSEO',
    category: 'Keyword and SERP data',
    summary: 'Search volume, SERP results, PAA data, and competitor keyword discovery.',
    usedBy: 'keyword-discovery, serp-analyzer, competitor research',
    setup: 'manual',
    docsHref: 'https://app.dataforseo.com',
    fields: [
      { key: 'login', label: 'API login', placeholder: 'your DataForSEO login', required: true },
      {
        key: 'password',
        label: 'API password',
        type: 'password',
        placeholder: 'your DataForSEO password',
        required: true,
      },
    ],
  },
  {
    kind: 'firecrawl',
    name: 'Firecrawl',
    category: 'Crawling and extraction',
    summary: 'Scrape source pages, competitor pages, SERPs, and drift snapshots.',
    usedBy: 'serp-analyzer, content-brief, drift-watch, Google PAA',
    setup: 'manual',
    docsHref: 'https://firecrawl.dev',
    fields: [
      {
        key: 'api_key',
        label: 'API key',
        type: 'password',
        placeholder: 'fc-...',
        required: true,
      },
    ],
  },
  {
    kind: 'gsc',
    name: 'Google Search Console',
    category: 'Performance and indexing',
    summary: 'Search analytics, indexing inspection, crawl errors, and opportunity mining.',
    usedBy: 'weekly-gsc-review, gsc-opportunity-finder, crawl-error-watch',
    setup: 'oauth',
    docsHref: 'https://console.cloud.google.com',
  },
  {
    kind: 'openai-images',
    name: 'OpenAI Images',
    category: 'Article images',
    summary: 'Hero, inline, and social image generation through the daemon image wrapper.',
    usedBy: 'image-generator',
    setup: 'manual',
    docsHref: 'https://platform.openai.com/api-keys',
    fields: [
      {
        key: 'api_key',
        label: 'Image API key',
        type: 'password',
        placeholder: 'sk-...',
        required: true,
      },
    ],
  },
  {
    kind: 'reddit',
    name: 'Reddit',
    category: 'Audience research',
    summary: 'Application-only Reddit search for questions and pain points.',
    usedBy: 'keyword-discovery',
    setup: 'manual',
    docsHref: 'https://www.reddit.com/prefs/apps',
    fields: [
      { key: 'client_id', label: 'Client ID', placeholder: 'app client id', required: true },
      {
        key: 'client_secret',
        label: 'Client secret',
        type: 'password',
        placeholder: 'app client secret',
        required: true,
      },
      {
        key: 'user_agent',
        label: 'User agent',
        placeholder: 'content-stack/0.1 by your-username',
        required: true,
      },
    ],
  },
  {
    kind: 'jina',
    name: 'Jina Reader',
    category: 'Markdown fallback',
    summary: 'Optional reader API key for higher limits when extracting pages as markdown.',
    usedBy: 'serp-analyzer markdown fallback',
    setup: 'manual',
    optional: true,
    docsHref: 'https://jina.ai/reader',
    fields: [
      {
        key: 'api_key',
        label: 'API key',
        type: 'password',
        placeholder: 'optional Jina key',
        required: true,
      },
    ],
  },
  {
    kind: 'ahrefs',
    name: 'Ahrefs',
    category: 'Enterprise competitor data',
    summary: 'Optional enterprise API for keyword inventory and backlink research.',
    usedBy: 'keyword-discovery, one-site-shortcut',
    setup: 'manual',
    optional: true,
    docsHref: 'https://ahrefs.com/api',
    fields: [
      {
        key: 'api_key',
        label: 'API token',
        type: 'password',
        placeholder: 'Ahrefs enterprise token',
        required: true,
      },
    ],
  },
  {
    kind: 'google-paa',
    name: 'Google People Also Ask',
    category: 'Question mining',
    summary: 'No direct key. Uses Firecrawl to fetch SERP pages and extract questions.',
    usedBy: 'keyword-discovery',
    setup: 'none',
    dependsOn: ['firecrawl'],
  },
]

const vendorByKind = new Map(vendors.map((vendor) => [vendor.kind, vendor]))

const allCreds = ref<Cred[]>([])
const loading = ref(false)
const activeKind = ref<VendorKind | null>(null)
const formFields = ref<Record<string, string>>({})
const saving = ref(false)
const testingIds = ref<Set<number>>(new Set())
const connectingGsc = ref(false)

const projectCreds = computed(() => allCreds.value.filter((c) => c.project_id === projectId.value))
const globalCreds = computed(() => allCreds.value.filter((c) => c.project_id === null))

const projectCredByKind = computed(() => {
  const map = new Map<string, Cred>()
  for (const cred of projectCreds.value) map.set(cred.kind, cred)
  return map
})

const globalCredByKind = computed(() => {
  const map = new Map<string, Cred>()
  for (const cred of globalCreds.value) map.set(cred.kind, cred)
  return map
})

const requiredKinds = computed<VendorKind[]>(() => {
  const raw = route.query.required
  const joined = Array.isArray(raw) ? raw.join(',') : raw ?? ''
  const kinds = joined
    .split(',')
    .map((item) => normalizeKind(item.trim()))
    .filter((item): item is VendorKind => item !== null)
  return [...new Set(kinds)]
})

const requiredVendors = computed(() => requiredKinds.value.map((kind) => vendorByKind.get(kind)!))

const setupLink = computed(() => {
  const origin = window.location.origin
  const suffix =
    requiredKinds.value.length > 0 ? `?required=${requiredKinds.value.join(',')}` : ''
  return `${origin}/projects/${projectId.value}/integrations${suffix}`
})

const activeVendor = computed(() => (activeKind.value ? vendorByKind.get(activeKind.value) : null))
const activeCredential = computed(() =>
  activeKind.value ? projectCredByKind.value.get(activeKind.value) : undefined,
)

function normalizeKind(kind: string): VendorKind | null {
  const normalized = kind.toLowerCase().replace(/_/g, '-')
  if (normalized === 'paa') return 'google-paa'
  if (normalized === 'openai') return 'openai-images'
  return vendorByKind.has(normalized as VendorKind) ? (normalized as VendorKind) : null
}

function credentialFor(kind: VendorKind): Cred | undefined {
  return projectCredByKind.value.get(kind) ?? globalCredByKind.value.get(kind)
}

function isProjectCredential(kind: VendorKind): boolean {
  return projectCredByKind.value.has(kind)
}

function isConnected(kind: VendorKind): boolean {
  if (kind === 'google-paa') return isConnected('firecrawl')
  return credentialFor(kind) !== undefined
}

function statusLabel(kind: VendorKind): string {
  if (kind === 'google-paa') return isConnected('firecrawl') ? 'Ready' : 'Needs Firecrawl'
  if (isProjectCredential(kind)) return 'Connected'
  if (globalCredByKind.value.has(kind)) return 'Using global'
  return 'Not connected'
}

function statusClass(kind: VendorKind): string {
  if (isConnected(kind)) {
    return 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200'
  }
  if (requiredKinds.value.includes(kind)) {
    return 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200'
  }
  return 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300'
}

function initialFields(vendor: VendorSpec, cred?: Cred): Record<string, string> {
  const config = (cred?.config_json ?? {}) as Record<string, unknown>
  const initial: Record<string, string> = {}
  for (const field of vendor.fields ?? []) {
    const configValue = config[field.key]
    initial[field.key] = typeof configValue === 'string' ? configValue : ''
  }
  if (vendor.kind === 'reddit') {
    initial.user_agent ||= 'content-stack/0.1 by your-username'
  }
  return initial
}

function openSetup(kind: VendorKind): void {
  const vendor = vendorByKind.get(kind)
  if (!vendor || vendor.setup !== 'manual') return
  activeKind.value = kind
  formFields.value = initialFields(vendor, projectCredByKind.value.get(kind))
}

function closeSetup(): void {
  if (saving.value) return
  activeKind.value = null
  formFields.value = {}
}

function payloadFor(vendor: VendorSpec): string {
  const fields = formFields.value
  if (vendor.kind === 'dataforseo') return fields.password?.trim() ?? ''
  if (vendor.kind === 'reddit') {
    return JSON.stringify({
      client_id: fields.client_id?.trim() ?? '',
      client_secret: fields.client_secret?.trim() ?? '',
      user_agent: fields.user_agent?.trim() ?? '',
    })
  }
  return fields.api_key?.trim() ?? ''
}

function configFor(vendor: VendorSpec): Record<string, unknown> {
  const fields = formFields.value
  if (vendor.kind === 'dataforseo') return { login: fields.login?.trim() ?? '' }
  if (vendor.kind === 'reddit') {
    return {
      client_id: fields.client_id?.trim() ?? '',
      user_agent: fields.user_agent?.trim() ?? '',
    }
  }
  return {}
}

function validateFields(vendor: VendorSpec): boolean {
  for (const field of vendor.fields ?? []) {
    if (field.required && !formFields.value[field.key]?.trim()) {
      toasts.error(`${field.label} is required`)
      return false
    }
  }
  return true
}

async function load(): Promise<void> {
  if (!projectId.value || Number.isNaN(projectId.value)) return
  loading.value = true
  try {
    const res = await apiFetch<Cred[]>(`/api/v1/projects/${projectId.value}/integrations`)
    allCreds.value = Array.isArray(res) ? res : []
  } catch (err) {
    toasts.error('Failed to load integrations', err instanceof Error ? err.message : undefined)
  } finally {
    loading.value = false
  }
}

async function saveManual(): Promise<void> {
  const vendor = activeVendor.value
  if (!vendor || vendor.setup !== 'manual') return
  if (!validateFields(vendor)) return
  const payload = payloadFor(vendor)
  if (!payload) {
    toasts.error('Credential value is required')
    return
  }
  saving.value = true
  try {
    const body = {
      kind: vendor.kind,
      plaintext_payload: payload,
      config_json: configFor(vendor),
    }
    const existing = activeCredential.value
    if (existing) {
      await apiWrite<Cred>(`/api/v1/projects/${projectId.value}/integrations/${existing.id}`, {
        method: 'PATCH',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(body),
      })
      toasts.success(`${vendor.name} updated`)
    } else {
      await apiWrite<Cred>(`/api/v1/projects/${projectId.value}/integrations`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(body),
      })
      toasts.success(`${vendor.name} connected`)
    }
    closeSetup()
    await load()
  } catch (err) {
    toasts.error(`Failed to save ${vendor.name}`, err instanceof Error ? err.message : undefined)
  } finally {
    saving.value = false
  }
}

async function remove(cred: Cred, vendor: VendorSpec): Promise<void> {
  try {
    await apiWrite<Cred>(`/api/v1/projects/${projectId.value}/integrations/${cred.id}`, {
      method: 'DELETE',
    })
    toasts.success(`${vendor.name} removed`)
    if (activeKind.value === vendor.kind) closeSetup()
    await load()
  } catch (err) {
    toasts.error(`Failed to remove ${vendor.name}`, err instanceof Error ? err.message : undefined)
  }
}

function setTesting(id: number, on: boolean): void {
  const next = new Set(testingIds.value)
  if (on) next.add(id)
  else next.delete(id)
  testingIds.value = next
}

async function testCredential(cred: Cred, vendor: VendorSpec): Promise<void> {
  setTesting(cred.id, true)
  try {
    const res = await apiFetch<TestResult>(
      `/api/v1/projects/${projectId.value}/integrations/${cred.id}/test`,
      { method: 'POST' },
    )
    const ok = res.ok ?? res.status === 'ok'
    if (ok) {
      toasts.success(`${vendor.name} test passed`, res.detail ?? res.message)
    } else {
      toasts.error(`${vendor.name} test failed`, res.detail ?? res.message)
    }
  } catch (err) {
    if (err instanceof ApiError) {
      toasts.error(`${vendor.name} test failed`, `HTTP ${err.status}`)
    } else {
      toasts.error(`${vendor.name} test failed`, err instanceof Error ? err.message : undefined)
    }
  } finally {
    setTesting(cred.id, false)
  }
}

async function connectGsc(): Promise<void> {
  connectingGsc.value = true
  const popup = window.open('about:blank', '_blank')
  try {
    const res = await apiFetch<{ authorization_url: string }>(
      '/api/v1/integrations/gsc/oauth/authorize',
      {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ project_id: projectId.value }),
      },
    )
    if (popup) {
      popup.opener = null
      popup.location.href = res.authorization_url
    } else {
      window.location.assign(res.authorization_url)
    }
    toasts.info('Google authorization opened', 'Return here and refresh after consent.')
    await load()
  } catch (err) {
    popup?.close()
    toasts.error(
      'Failed to start Google authorization',
      err instanceof Error ? err.message : undefined,
    )
  } finally {
    connectingGsc.value = false
  }
}

async function copySetupLink(): Promise<void> {
  try {
    await navigator.clipboard.writeText(setupLink.value)
    toasts.success('Integration link copied')
  } catch {
    toasts.error('Could not copy link', setupLink.value)
  }
}

onMounted(load)
watch(projectId, load)
</script>

<template>
  <section class="space-y-6">
    <div class="flex flex-wrap items-start justify-between gap-4">
      <div>
        <h2 class="text-base font-semibold">
          Vendor connections
        </h2>
        <p class="mt-1 max-w-3xl text-sm text-gray-600 dark:text-gray-400">
          Connect the services this project needs. Secrets are encrypted in the local daemon
          and never written to the website repository.
        </p>
      </div>
      <div class="flex flex-wrap gap-2">
        <button
          type="button"
          class="rounded border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-100 dark:border-gray-700 dark:hover:bg-gray-800"
          @click="copySetupLink"
        >
          Copy setup link
        </button>
        <button
          type="button"
          class="rounded border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-100 dark:border-gray-700 dark:hover:bg-gray-800"
          :disabled="loading"
          @click="load"
        >
          {{ loading ? 'Refreshing…' : 'Refresh' }}
        </button>
      </div>
    </div>

    <div
      v-if="requiredVendors.length > 0"
      class="rounded-md border border-amber-200 bg-amber-50 p-4 dark:border-amber-900/70 dark:bg-amber-950/30"
    >
      <h3 class="text-sm font-semibold text-amber-900 dark:text-amber-100">
        Needed for the current agent flow
      </h3>
      <ul class="mt-2 flex flex-wrap gap-2 text-sm">
        <li
          v-for="vendor in requiredVendors"
          :key="vendor.kind"
          class="rounded bg-white px-2 py-1 text-amber-900 shadow-sm dark:bg-amber-900/40 dark:text-amber-50"
        >
          {{ vendor.name }} · {{ statusLabel(vendor.kind) }}
        </li>
      </ul>
    </div>

    <div class="grid gap-4 xl:grid-cols-2">
      <article
        v-for="vendor in vendors"
        :key="vendor.kind"
        class="rounded-md border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900"
        :class="requiredKinds.includes(vendor.kind) && !isConnected(vendor.kind) ? 'ring-2 ring-amber-300 dark:ring-amber-700' : ''"
      >
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div class="flex flex-wrap items-center gap-2">
              <h3 class="text-base font-semibold">
                {{ vendor.name }}
              </h3>
              <span
                class="rounded px-2 py-0.5 text-xs font-medium"
                :class="statusClass(vendor.kind)"
              >
                {{ statusLabel(vendor.kind) }}
              </span>
              <span
                v-if="vendor.optional"
                class="rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-700 dark:bg-gray-800 dark:text-gray-300"
              >
                Optional
              </span>
            </div>
            <p class="mt-1 text-sm text-gray-600 dark:text-gray-400">
              {{ vendor.summary }}
            </p>
          </div>
        </div>

        <dl class="mt-3 grid gap-2 text-sm sm:grid-cols-2">
          <div>
            <dt class="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
              Used by
            </dt>
            <dd class="mt-0.5 text-gray-800 dark:text-gray-200">
              {{ vendor.usedBy }}
            </dd>
          </div>
          <div>
            <dt class="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
              Agent tool key
            </dt>
            <dd class="mt-0.5 font-mono text-xs text-gray-700 dark:text-gray-300">
              {{ vendor.kind }}
            </dd>
          </div>
        </dl>

        <p
          v-if="vendor.dependsOn?.length"
          class="mt-3 text-sm text-gray-600 dark:text-gray-400"
        >
          Uses {{ vendor.dependsOn.map((kind) => vendorByKind.get(kind)?.name ?? kind).join(', ') }}.
        </p>

        <div class="mt-4 flex flex-wrap gap-2">
          <button
            v-if="vendor.setup === 'manual'"
            type="button"
            class="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
            @click="openSetup(vendor.kind)"
          >
            {{ isProjectCredential(vendor.kind) ? 'Update connection' : 'Connect' }}
          </button>
          <button
            v-else-if="vendor.setup === 'oauth'"
            type="button"
            class="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            :disabled="connectingGsc"
            @click="connectGsc"
          >
            {{ connectingGsc ? 'Opening…' : isConnected(vendor.kind) ? 'Reconnect Google' : 'Connect Google' }}
          </button>
          <a
            v-if="vendor.docsHref"
            :href="vendor.docsHref"
            target="_blank"
            rel="noreferrer"
            class="rounded border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-100 dark:border-gray-700 dark:hover:bg-gray-800"
          >
            Get credentials
          </a>
          <button
            v-if="credentialFor(vendor.kind) && vendor.setup !== 'none'"
            type="button"
            class="rounded border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-100 disabled:opacity-50 dark:border-gray-700 dark:hover:bg-gray-800"
            :disabled="testingIds.has(credentialFor(vendor.kind)!.id)"
            @click="testCredential(credentialFor(vendor.kind)!, vendor)"
          >
            {{ testingIds.has(credentialFor(vendor.kind)!.id) ? 'Testing…' : 'Test' }}
          </button>
          <button
            v-if="isProjectCredential(vendor.kind)"
            type="button"
            class="rounded border border-red-300 px-3 py-1.5 text-sm font-medium text-red-700 hover:bg-red-50 dark:border-red-800 dark:text-red-300 dark:hover:bg-red-900/30"
            @click="remove(projectCredByKind.get(vendor.kind)!, vendor)"
          >
            Remove
          </button>
        </div>

        <p
          v-if="globalCredByKind.has(vendor.kind) && !projectCredByKind.has(vendor.kind)"
          class="mt-3 text-xs text-gray-500 dark:text-gray-400"
        >
          This project is using a global credential. Connect here to override it for this project.
        </p>
      </article>
    </div>

    <div
      v-if="activeVendor"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="cs-integration-form-title"
      @click.self="closeSetup"
    >
      <div
        class="w-full max-w-lg rounded-lg border border-gray-200 bg-white p-5 shadow-xl dark:border-gray-700 dark:bg-gray-900"
      >
        <h3
          id="cs-integration-form-title"
          class="text-lg font-semibold"
        >
          {{ activeCredential ? `Update ${activeVendor.name}` : `Connect ${activeVendor.name}` }}
        </h3>
        <p class="mt-1 text-sm text-gray-600 dark:text-gray-400">
          Paste the credential here. The daemon encrypts it before storing it.
          Existing secret values cannot be displayed, so updates require pasting the secret again.
        </p>

        <div class="mt-4 space-y-3">
          <label
            v-for="field in activeVendor.fields"
            :key="field.key"
            class="block text-sm"
          >
            <span class="font-medium">{{ field.label }}</span>
            <input
              v-model="formFields[field.key]"
              :type="field.type ?? 'text'"
              :placeholder="field.placeholder"
              :autocomplete="field.type === 'password' ? 'new-password' : 'off'"
              class="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-800"
            >
            <span
              v-if="field.help"
              class="mt-1 block text-xs text-gray-500 dark:text-gray-400"
            >
              {{ field.help }}
            </span>
          </label>
        </div>

        <div class="mt-5 flex justify-end gap-2">
          <button
            type="button"
            class="rounded border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-100 dark:border-gray-700 dark:hover:bg-gray-800"
            :disabled="saving"
            @click="closeSetup"
          >
            Cancel
          </button>
          <button
            type="button"
            class="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            :disabled="saving"
            @click="saveManual"
          >
            {{ saving ? 'Saving…' : activeCredential ? 'Save connection' : 'Connect vendor' }}
          </button>
        </div>
      </div>
    </div>
  </section>
</template>
