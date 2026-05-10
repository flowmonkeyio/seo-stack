<script setup lang="ts">
// ArticleDetailView — the heaviest single view in M5.
//
// Top of view:
//   1. Breadcrumb: project name → "Articles" → title
//   2. Header: title (h1) + slug + StatusBadge + version + author bylines
//   3. Status timeline: stepper through briefing → outlined → drafted →
//      edited → eeat_passed → published. Current = ring; completed = check;
//      future = muted.
//   4. Action bar: typed-verb buttons appropriate to current status. Each
//      button passes `expected_etag` from the article's current step_etag
//      and shows loading + ETag-mismatch handling.
//   5. TabBar: 12 tabs (brief/outline/draft/edited/assets/sources/schema/
//      publishes/eeat/versions/interlinks/drift). Each tab is a child route.

import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter, RouterView } from 'vue-router'

import StatusBadge from '@/components/StatusBadge.vue'
import TabBar from '@/components/TabBar.vue'
import {
  UiBreadcrumbs,
  UiButton,
  UiPageHeader,
  UiPageShell,
} from '@/components/ui'
import {
  useArticlesStore,
  ArticleEtagError,
  type Article,
  type ArticleStatus,
} from '@/stores/articles'
import { useProjectsStore } from '@/stores/projects'
import { useToastsStore } from '@/stores/toasts'
import { apiFetch } from '@/lib/client'
import { ArticleStatus as ArticleStatusEnum, type components } from '@/api'

type Author = components['schemas']['AuthorOut']

const route = useRoute()
const router = useRouter()
const articlesStore = useArticlesStore()
const projectsStore = useProjectsStore()
const toasts = useToastsStore()

const projectId = computed<number>(() => Number.parseInt(route.params.id as string, 10))
const articleId = computed<number>(() => Number.parseInt(route.params.aid as string, 10))

const article = computed<Article | null>(() => articlesStore.currentDetail)
const project = computed(() => projectsStore.getById(projectId.value))

const author = ref<Author | null>(null)
const reviewer = ref<Author | null>(null)
const loadingArticle = ref(false)

const tabs = computed(() => [
  { key: 'brief', label: 'Brief' },
  { key: 'outline', label: 'Outline' },
  { key: 'draft', label: 'Draft' },
  { key: 'edited', label: 'Edited' },
  { key: 'assets', label: 'Assets' },
  { key: 'sources', label: 'Sources' },
  { key: 'schema', label: 'Schema' },
  { key: 'publishes', label: 'Publishes' },
  { key: 'eeat', label: 'EEAT' },
  { key: 'versions', label: 'Versions' },
  { key: 'interlinks', label: 'Interlinks' },
  { key: 'drift', label: 'Drift' },
])

const activeKey = computed<string>(() => {
  const name = String(route.name ?? '')
  const match = name.match(/^project-article-detail-(.+)$/)
  return match ? match[1] : 'brief'
})

function onTabChange(key: string): void {
  void router.push(`/projects/${projectId.value}/articles/${articleId.value}/${key}`)
}

const STATUS_STEPS: { key: `${ArticleStatusEnum}`; label: string }[] = [
  { key: 'briefing', label: 'Briefing' },
  { key: 'outlined', label: 'Outlined' },
  { key: 'drafted', label: 'Drafted' },
  { key: 'edited', label: 'Edited' },
  { key: 'eeat_passed', label: 'EEAT Passed' },
  { key: 'published', label: 'Published' },
]

const currentStepIndex = computed<number>(() => {
  const status = article.value?.status as ArticleStatus | undefined
  if (!status) return 0
  if (status === 'aborted-publish' || status === 'refresh_due') {
    return STATUS_STEPS.length - 1
  }
  return STATUS_STEPS.findIndex((s) => s.key === status)
})

function stepClasses(idx: number, current: number): string {
  if (idx < current)
    return 'bg-success text-fg-on-accent border-success'
  if (idx === current)
    return 'bg-accent text-fg-on-accent border-accent ring-2 ring-focus'
  return 'bg-bg-surface text-fg-muted border-default'
}

function lineClasses(idx: number, current: number): string {
  return idx < current ? 'bg-success' : 'bg-border-default'
}

const actionBusy = ref<string | null>(null)

async function reloadArticle(): Promise<void> {
  await articlesStore.get(articleId.value)
}

async function runVerb(name: string, fn: () => Promise<unknown>): Promise<void> {
  actionBusy.value = name
  try {
    await fn()
  } catch (err) {
    if (err instanceof ArticleEtagError) {
      toasts.error('Stale article version', 'Reloading the article…')
      await reloadArticle()
    } else {
      toasts.error(`${name} failed`, err instanceof Error ? err.message : undefined)
    }
  } finally {
    actionBusy.value = null
  }
}

async function actionMarkDrafted(): Promise<void> {
  if (!article.value?.step_etag) return
  await runVerb('mark drafted', () =>
    articlesStore.markDrafted(articleId.value, { expected_etag: article.value!.step_etag! }),
  )
}

async function actionMarkEeatPassed(): Promise<void> {
  if (!article.value?.step_etag) return
  await runVerb('mark EEAT passed', () =>
    articlesStore.markEeatPassed(articleId.value, {
      expected_etag: article.value!.step_etag!,
      eeat_criteria_version: article.value!.eeat_criteria_version_used ?? 1,
    }),
  )
}

async function actionMarkPublished(): Promise<void> {
  if (!article.value?.step_etag) return
  await runVerb('publish', () =>
    articlesStore.markPublished(articleId.value, {
      expected_etag: article.value!.step_etag!,
    }),
  )
}

async function actionMarkRefreshDue(): Promise<void> {
  if (!article.value) return
  await runVerb('mark refresh due', () =>
    articlesStore.markRefreshDue(articleId.value, { reason: 'manual-refresh-from-ui' }),
  )
}

async function actionCreateVersion(): Promise<void> {
  if (!article.value) return
  await runVerb('create version', async () => {
    await articlesStore.createVersion(articleId.value)
    toasts.success('Version snapshot created')
  })
}

function gotoTab(key: string): void {
  void router.push(`/projects/${projectId.value}/articles/${articleId.value}/${key}`)
}

async function loadAuthors(): Promise<void> {
  if (!article.value) return
  const ids = [article.value.author_id, article.value.reviewer_author_id].filter(
    (n): n is number => n !== null,
  )
  if (ids.length === 0) return
  try {
    const params = new URLSearchParams({ limit: '200' })
    const page = await apiFetch<components['schemas']['PageResponse_AuthorOut_']>(
      `/api/v1/projects/${projectId.value}/authors?${params.toString()}`,
    )
    const idx = new Map(page.items.map((a) => [a.id, a]))
    author.value = article.value.author_id !== null ? idx.get(article.value.author_id) ?? null : null
    reviewer.value =
      article.value.reviewer_author_id !== null
        ? idx.get(article.value.reviewer_author_id) ?? null
        : null
  } catch {
    author.value = null
    reviewer.value = null
  }
}

async function loadAll(): Promise<void> {
  if (!articleId.value || Number.isNaN(articleId.value)) return
  loadingArticle.value = true
  try {
    await articlesStore.get(articleId.value)
    if (projectsStore.items.length === 0) await projectsStore.refresh()
    await loadAuthors()
  } catch (err) {
    toasts.error('Failed to load article', err instanceof Error ? err.message : undefined)
  } finally {
    loadingArticle.value = false
  }
}

const isUnscored = computed(() => article.value?.status === 'briefing')

const breadcrumbItems = computed(() => [
  { label: 'Projects', to: '/projects' },
  {
    label: project.value?.name ?? `Project ${projectId.value}`,
    to: `/projects/${projectId.value}/overview`,
  },
  { label: 'Articles', to: `/projects/${projectId.value}/articles` },
  { label: article.value?.title ?? 'Article' },
])

onMounted(async () => {
  await loadAll()
  // If the URL is /projects/:id/articles/:aid (no tab), redirect to brief.
  if (route.name === 'project-article-detail') {
    void router.replace(
      `/projects/${projectId.value}/articles/${articleId.value}/brief`,
    )
  }
})

watch(articleId, loadAll)
</script>

<template>
  <UiPageShell>
    <UiPageHeader :title="article?.title ?? 'Loading…'">
      <template #breadcrumbs>
        <UiBreadcrumbs :items="breadcrumbItems" />
      </template>
      <template #titleMeta>
        <StatusBadge
          v-if="article"
          :status="article.status"
          kind="article"
        />
        <span
          v-if="article"
          class="rounded-xs bg-neutral-subtle px-2 py-0.5 text-xs text-neutral-fg"
        >
          v{{ article.version }}
        </span>
      </template>
      <template
        v-if="article"
        #meta
      >
        <span class="font-mono">{{ article.slug }}</span>
        <span v-if="author">author <strong class="font-medium text-fg-default">{{ author.name }}</strong></span>
        <span v-if="reviewer">reviewer <strong class="font-medium text-fg-default">{{ reviewer.name }}</strong></span>
      </template>
    </UiPageHeader>

    <ol
      v-if="article"
      class="flex items-center gap-2 overflow-x-auto rounded-md border border-subtle bg-bg-surface px-3 py-3"
      tabindex="0"
      aria-label="Article status timeline"
    >
      <template
        v-for="(step, idx) in STATUS_STEPS"
        :key="step.key"
      >
        <li class="flex flex-col items-center text-xs">
          <span
            class="flex h-7 w-7 items-center justify-center rounded-full border text-xs font-semibold transition"
            :class="stepClasses(idx, currentStepIndex)"
            :aria-current="idx === currentStepIndex ? 'step' : undefined"
          >
            <template v-if="idx < currentStepIndex">✓</template>
            <template v-else>{{ idx + 1 }}</template>
          </span>
          <span class="mt-1 whitespace-nowrap text-[11px] text-fg-muted">
            {{ step.label }}
          </span>
        </li>
        <li
          v-if="idx < STATUS_STEPS.length - 1"
          aria-hidden="true"
          class="h-0.5 flex-1 min-w-[2rem]"
          :class="lineClasses(idx, currentStepIndex)"
        />
      </template>
    </ol>

    <div
      v-if="article"
      class="flex flex-wrap items-center gap-2"
    >
      <UiButton
        v-if="article.status === 'briefing'"
        size="sm"
        variant="primary"
        @click="gotoTab('brief')"
      >
        Edit brief
      </UiButton>

      <UiButton
        v-if="article.status === 'outlined'"
        size="sm"
        variant="primary"
        @click="gotoTab('draft')"
      >
        Continue to draft
      </UiButton>

      <UiButton
        v-if="article.status === 'outlined'"
        size="sm"
        variant="secondary"
        :disabled="actionBusy !== null"
        @click="actionMarkDrafted"
      >
        {{ actionBusy === 'mark drafted' ? 'Marking…' : 'Mark drafted' }}
      </UiButton>

      <UiButton
        v-if="article.status === 'drafted'"
        size="sm"
        variant="primary"
        @click="gotoTab('edited')"
      >
        Continue to editor
      </UiButton>

      <UiButton
        v-if="article.status === 'edited'"
        size="sm"
        variant="secondary"
        :disabled="actionBusy !== null"
        @click="actionMarkEeatPassed"
      >
        {{ actionBusy === 'mark EEAT passed' ? 'Marking…' : 'Mark EEAT passed (manual)' }}
      </UiButton>

      <UiButton
        v-if="article.status === 'eeat_passed'"
        size="sm"
        variant="primary"
        :disabled="actionBusy !== null"
        @click="actionMarkPublished"
      >
        {{ actionBusy === 'publish' ? 'Publishing…' : 'Publish' }}
      </UiButton>

      <UiButton
        v-if="article.status === 'published'"
        size="sm"
        variant="secondary"
        :disabled="actionBusy !== null"
        @click="actionMarkRefreshDue"
      >
        Mark refresh due
      </UiButton>

      <UiButton
        size="sm"
        variant="secondary"
        :disabled="actionBusy !== null"
        @click="actionCreateVersion"
      >
        New version
      </UiButton>
    </div>

    <p
      v-if="!article && !loadingArticle"
      class="rounded-md border border-dashed border-default p-4 text-sm text-fg-muted"
    >
      Article not found.
    </p>

    <p
      v-else-if="loadingArticle && !article"
      class="rounded-md border border-dashed border-default p-4 text-sm text-fg-muted"
    >
      Loading article…
    </p>

    <template v-else>
      <TabBar
        :tabs="tabs"
        :active-key="activeKey"
        aria-label="Article sections"
        @change="onTabChange"
      />
      <div
        :id="`cs-tabpanel-${activeKey}`"
        role="tabpanel"
        :aria-labelledby="`cs-tab-${activeKey}`"
        class="pt-3"
      >
        <RouterView
          v-if="article"
          :article-id="articleId"
          :project-id="projectId"
        />
      </div>
    </template>

    <p
      v-if="isUnscored"
      class="text-xs text-fg-muted"
    >
      Article is in <code>briefing</code>. Save the brief to advance the
      timeline.
    </p>
  </UiPageShell>
</template>
