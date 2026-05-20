<script setup lang="ts">
// IntegrationsTab — read-only vendor readiness console.

import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { UiBadge, UiButton, UiCallout, UiSectionHeader } from '@/components/ui'
import { apiFetch, formatApiError } from '@/lib/client'
import { useToastsStore } from '@/stores/toasts'
import type { components } from '@/api'

type Cred = components['schemas']['IntegrationCredentialOut']
type GscOAuthInfo = components['schemas']['GscOAuthInfoResponse']

type VendorKind =
  | 'dataforseo'
  | 'firecrawl'
  | 'gsc'
  | 'openai-images'
  | 'reddit'
  | 'jina'
  | 'ahrefs'
  | 'google-paa'
  | 'wordpress'
  | 'ghost'
type VendorWorkflow = 'research' | 'monitoring' | 'assets' | 'publishing' | 'optional'

interface VendorSpec {
  kind: VendorKind
  name: string
  workflow: VendorWorkflow
  category: string
  summary: string
  usedBy: string
  setup: 'manual' | 'oauth' | 'none'
  dependsOn?: VendorKind[]
  optional?: boolean
  docsHref?: string
}

interface IntegrationSection {
  key: VendorWorkflow
  title: string
  description: string
  vendors: VendorSpec[]
}

const route = useRoute()
const toasts = useToastsStore()

const projectId = computed<number>(() => Number.parseInt(route.params.id as string, 10))

const vendors: VendorSpec[] = [
  {
    kind: 'dataforseo',
    name: 'DataForSEO',
    workflow: 'research',
    category: 'Keyword and SERP data',
    summary: 'Search volume, SERP results, PAA data, and competitor keyword discovery.',
    usedBy: 'keyword-discovery, serp-analyzer, competitor research',
    setup: 'manual',
    docsHref: 'https://app.dataforseo.com',
  },
  {
    kind: 'firecrawl',
    name: 'Firecrawl',
    workflow: 'research',
    category: 'Crawling and extraction',
    summary: 'Scrape source pages, competitor pages, SERPs, and drift snapshots.',
    usedBy: 'serp-analyzer, content-brief, drift-watch, Google PAA',
    setup: 'manual',
    docsHref: 'https://firecrawl.dev',
  },
  {
    kind: 'gsc',
    name: 'Google Search Console',
    workflow: 'monitoring',
    category: 'Performance and indexing',
    summary: 'Search analytics, indexing inspection, crawl errors, and opportunity mining.',
    usedBy: 'weekly-gsc-review, gsc-opportunity-finder, crawl-error-watch',
    setup: 'oauth',
    docsHref: 'https://console.cloud.google.com',
  },
  {
    kind: 'openai-images',
    name: 'OpenAI Images',
    workflow: 'assets',
    category: 'Article images',
    summary: 'Hero, inline, and social image generation through the daemon image wrapper.',
    usedBy: 'image-generator',
    setup: 'manual',
    docsHref: 'https://platform.openai.com/api-keys',
  },
  {
    kind: 'wordpress',
    name: 'WordPress',
    workflow: 'publishing',
    category: 'Publishing destination',
    summary: 'Publish edited articles and media through the WordPress REST API.',
    usedBy: 'wordpress-publish',
    setup: 'manual',
    docsHref: 'https://wordpress.org/documentation/article/application-passwords/',
  },
  {
    kind: 'ghost',
    name: 'Ghost',
    workflow: 'publishing',
    category: 'Publishing destination',
    summary: 'Publish edited articles, authors, tags, and images through the Ghost Admin API.',
    usedBy: 'ghost-publish',
    setup: 'manual',
    docsHref: 'https://ghost.org/docs/admin-api/',
  },
  {
    kind: 'reddit',
    name: 'Reddit',
    workflow: 'optional',
    category: 'Audience research',
    summary: 'Subreddit searches and recurring question discovery.',
    usedBy: 'keyword-discovery',
    setup: 'manual',
    optional: true,
    docsHref: 'https://www.reddit.com/prefs/apps',
  },
  {
    kind: 'jina',
    name: 'Jina Reader',
    workflow: 'optional',
    category: 'Readable source extraction',
    summary: 'Markdown extraction fallback for pages where standard scraping is noisy.',
    usedBy: 'serp-analyzer, content-brief',
    setup: 'manual',
    optional: true,
    docsHref: 'https://jina.ai/reader/',
  },
  {
    kind: 'ahrefs',
    name: 'Ahrefs',
    workflow: 'optional',
    category: 'Competitor research',
    summary: 'Competitor keyword inventory and backlink discovery.',
    usedBy: 'competitor-sitemap-shortcut',
    setup: 'manual',
    optional: true,
    docsHref: 'https://app.ahrefs.com/user/api',
  },
  {
    kind: 'google-paa',
    name: 'Google PAA',
    workflow: 'optional',
    category: 'SERP question extraction',
    summary: 'People Also Ask extraction through the Firecrawl-backed helper.',
    usedBy: 'keyword-discovery',
    setup: 'none',
    dependsOn: ['firecrawl'],
    optional: true,
  },
]

const sectionOrder: VendorWorkflow[] = ['research', 'monitoring', 'assets', 'publishing', 'optional']
const sectionMeta: Record<VendorWorkflow, { title: string; description: string }> = {
  research: {
    title: 'Research',
    description: 'Data sources for keyword discovery, SERP analysis, briefs, and competitor mapping.',
  },
  monitoring: {
    title: 'Monitoring',
    description: 'Search Console and indexing signals used by ongoing agent reviews.',
  },
  assets: {
    title: 'Assets',
    description: 'Image generation and asset creation support.',
  },
  publishing: {
    title: 'Publishing',
    description: 'CMS destinations used by publish skills after quality gates pass.',
  },
  optional: {
    title: 'Optional accelerators',
    description: 'Useful add-ons that improve research breadth but are not required for the core path.',
  },
}

const allCreds = ref<Cred[]>([])
const gscOAuthInfo = ref<GscOAuthInfo | null>(null)
const loading = ref(false)

const projectCredByKind = computed(() => {
  const map = new Map<string, Cred>()
  for (const cred of allCreds.value) {
    if (cred.project_id === projectId.value) map.set(cred.kind, cred)
  }
  return map
})

const globalCredByKind = computed(() => {
  const map = new Map<string, Cred>()
  for (const cred of allCreds.value) {
    if (cred.project_id === null) map.set(cred.kind, cred)
  }
  return map
})

const requiredKinds = computed<VendorKind[]>(() => {
  const raw = typeof route.query.required === 'string' ? route.query.required : ''
  return raw
    .split(',')
    .map((kind) => kind.trim())
    .filter((kind): kind is VendorKind => vendors.some((vendor) => vendor.kind === kind))
})

const requiredVendors = computed(() =>
  vendors.filter((vendor) => requiredKinds.value.includes(vendor.kind)),
)

const missingRequiredVendors = computed(() =>
  requiredVendors.value.filter((vendor) => !isConnected(vendor.kind)),
)

const integrationSections = computed<IntegrationSection[]>(() =>
  sectionOrder.map((key) => ({
    key,
    ...sectionMeta[key],
    vendors: vendors.filter((vendor) => vendor.workflow === key),
  })),
)

const setupLink = computed(
  () => `content-stack integrations setup --project ${projectId.value}`,
)

const gscMissingSummary = computed(() =>
  gscOAuthInfo.value?.missing?.length ? gscOAuthInfo.value.missing.join(', ') : '',
)

function credentialFor(kind: VendorKind): Cred | null {
  return projectCredByKind.value.get(kind) ?? globalCredByKind.value.get(kind) ?? null
}

function isConnected(kind: VendorKind): boolean {
  if (kind === 'google-paa') return isConnected('firecrawl')
  return credentialFor(kind) !== null
}

function isProjectCredential(kind: VendorKind): boolean {
  return projectCredByKind.value.has(kind)
}

function statusLabel(kind: VendorKind): string {
  if (kind === 'gsc' && gscOAuthInfo.value && !gscOAuthInfo.value.configured) return 'Needs env'
  if (isProjectCredential(kind)) return 'Project credential'
  if (globalCredByKind.value.has(kind)) return 'Global fallback'
  if (kind === 'google-paa' && isConnected('firecrawl')) return 'Via Firecrawl'
  return 'Not connected'
}

function statusTone(kind: VendorKind): 'success' | 'warning' | 'neutral' {
  if (isConnected(kind)) return 'success'
  return kind === 'google-paa' ? 'neutral' : 'warning'
}

function statusSummary(kind: VendorKind): string {
  const cred = credentialFor(kind)
  if (kind === 'google-paa') {
    return isConnected('firecrawl') ? 'Available through Firecrawl' : 'Waiting on Firecrawl'
  }
  if (!cred) return 'Setup needed'
  const refreshed = cred.last_refreshed_at
    ? `Last tested ${new Date(cred.last_refreshed_at).toLocaleString()}`
    : 'Not tested yet'
  return `${isProjectCredential(kind) ? 'Project credential' : 'Global fallback'} / ${refreshed}`
}

function dependencyLabel(vendor: VendorSpec): string {
  return (vendor.dependsOn ?? [])
    .map((kind) => vendors.find((entry) => entry.kind === kind)?.name ?? kind)
    .join(', ')
}

function cardToneClass(kind: VendorKind): string {
  if (isConnected(kind)) return 'border-success-border bg-success-subtle/30'
  if (requiredKinds.value.includes(kind)) return 'border-warning-border bg-warning-subtle/40'
  return 'border-default bg-bg-surface'
}

async function load(): Promise<void> {
  if (!projectId.value || Number.isNaN(projectId.value)) return
  loading.value = true
  try {
    const [res, oauthInfo] = await Promise.all([
      apiFetch<Cred[]>(`/api/v1/projects/${projectId.value}/integrations`),
      apiFetch<GscOAuthInfo>('/api/v1/integrations/gsc/oauth/info'),
    ])
    allCreds.value = Array.isArray(res) ? res : []
    gscOAuthInfo.value = oauthInfo
  } catch (err) {
    toasts.error('Failed to load integrations', formatApiError(err))
  } finally {
    loading.value = false
  }
}

async function copySetupLink(): Promise<void> {
  try {
    await navigator.clipboard.writeText(setupLink.value)
    toasts.success('Integration handoff copied')
  } catch {
    toasts.error('Could not copy handoff', setupLink.value)
  }
}

onMounted(load)
watch(projectId, load)
</script>

<template>
  <section class="space-y-6">
    <UiSectionHeader
      title="Vendor connections"
      description="Readiness for the services this project uses. Credential changes are agent-owned through MCP."
    >
      <template #actions>
        <UiButton
          variant="secondary"
          size="sm"
          @click="copySetupLink"
        >
          Copy setup link
        </UiButton>
        <UiButton
          variant="secondary"
          size="sm"
          :disabled="loading"
          @click="load"
        >
          {{ loading ? 'Refreshing…' : 'Refresh' }}
        </UiButton>
      </template>
    </UiSectionHeader>

    <UiCallout
      v-if="requiredVendors.length > 0"
      :tone="missingRequiredVendors.length > 0 ? 'warning' : 'success'"
      title="Needed for the current agent flow"
    >
      <p class="mt-1 text-sm">
        {{
          missingRequiredVendors.length > 0
            ? 'Some required vendors still need agent setup.'
            : 'All required vendors are ready for this flow.'
        }}
      </p>
      <ul class="mt-3 flex flex-wrap gap-2 text-sm">
        <li
          v-for="vendor in requiredVendors"
          :key="vendor.kind"
        >
          <UiBadge
            :tone="isConnected(vendor.kind) ? 'success' : 'warning'"
            variant="outline"
          >
            {{ vendor.name }} / {{ statusLabel(vendor.kind) }}
          </UiBadge>
        </li>
      </ul>
    </UiCallout>

    <section
      v-for="section in integrationSections"
      :key="section.key"
      class="space-y-3"
      :aria-labelledby="`cs-${section.key}-integrations`"
    >
      <div>
        <h2
          :id="`cs-${section.key}-integrations`"
          class="text-base font-semibold text-fg-strong"
        >
          {{ section.title }}
        </h2>
        <p class="mt-0.5 text-sm text-fg-muted">
          {{ section.description }}
        </p>
      </div>

      <div class="grid gap-3">
        <article
          v-for="vendor in section.vendors"
          :key="vendor.kind"
          class="overflow-hidden rounded-md border shadow-xs transition-colors duration-fast"
          :class="cardToneClass(vendor.kind)"
        >
          <div class="space-y-4 p-4">
            <header class="flex flex-wrap items-start justify-between gap-3">
              <div class="min-w-0 space-y-1.5">
                <div class="flex flex-wrap items-center gap-2">
                  <h3 class="text-sm font-semibold text-fg-strong">
                    {{ vendor.name }}
                  </h3>
                  <UiBadge :tone="statusTone(vendor.kind)">
                    {{ statusLabel(vendor.kind) }}
                  </UiBadge>
                  <UiBadge
                    v-if="vendor.optional"
                    tone="neutral"
                  >
                    Optional
                  </UiBadge>
                  <UiBadge
                    v-if="requiredKinds.includes(vendor.kind)"
                    :tone="isConnected(vendor.kind) ? 'success' : 'warning'"
                  >
                    Required
                  </UiBadge>
                </div>
                <p class="text-sm text-fg-muted">
                  {{ vendor.summary }}
                </p>
              </div>
              <div class="text-right text-xs text-fg-muted">
                <div class="font-mono">
                  {{ vendor.kind }}
                </div>
                <div>{{ vendor.category }}</div>
                <a
                  v-if="vendor.docsHref"
                  :href="vendor.docsHref"
                  target="_blank"
                  rel="noreferrer"
                  class="mt-1 inline-block text-fg-link hover:underline"
                >
                  Credential docs
                </a>
              </div>
            </header>

            <dl class="grid gap-3 text-sm sm:grid-cols-[1fr_1.5fr]">
              <div>
                <dt class="text-[11px] font-semibold uppercase tracking-wide text-fg-subtle">
                  State
                </dt>
                <dd class="mt-1 text-fg-default">
                  {{ statusSummary(vendor.kind) }}
                </dd>
              </div>
              <div>
                <dt class="text-[11px] font-semibold uppercase tracking-wide text-fg-subtle">
                  Used by
                </dt>
                <dd class="mt-1 text-fg-default">
                  {{ vendor.usedBy }}
                </dd>
              </div>
            </dl>

            <div
              v-if="vendor.dependsOn?.length"
              class="rounded-md border border-subtle bg-bg-surface-alt px-3 py-2 text-sm text-fg-muted"
            >
              Depends on {{ dependencyLabel(vendor) }}.
            </div>

            <div
              v-if="vendor.kind === 'gsc' && gscOAuthInfo"
              class="rounded-md border border-subtle bg-bg-surface-alt px-3 py-2 text-sm"
            >
              <div class="flex flex-wrap items-center justify-between gap-2">
                <span class="text-[11px] font-semibold uppercase tracking-wide text-fg-subtle">
                  OAuth callback
                </span>
                <UiBadge :tone="gscOAuthInfo.configured ? 'success' : 'warning'">
                  {{ gscOAuthInfo.configured ? 'Configured' : 'Needs env' }}
                </UiBadge>
              </div>
              <div class="mt-1 break-all font-mono text-xs text-fg-default">
                {{ gscOAuthInfo.redirect_uri }}
              </div>
              <p
                v-if="!gscOAuthInfo.configured"
                class="mt-2 text-xs text-warning-fg"
              >
                Missing {{ gscMissingSummary }}
              </p>
            </div>

            <div class="border-t border-subtle pt-3 text-xs font-medium text-fg-muted">
              {{ isConnected(vendor.kind) ? 'Ready to use' : 'Agent setup needed' }}
            </div>
          </div>
        </article>
      </div>
    </section>
  </section>
</template>
