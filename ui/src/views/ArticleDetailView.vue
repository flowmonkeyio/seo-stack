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
import { useRoute, useRouter, RouterLink, RouterView } from 'vue-router'

import StatusBadge from '@/components/StatusBadge.vue'
import TabBar from '@/components/TabBar.vue'
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
    return 'bg-emerald-500 text-white border-emerald-500'
  if (idx === current)
    return 'bg-blue-600 text-white border-blue-600 ring-2 ring-blue-300 dark:ring-blue-800'
  return 'bg-white text-gray-500 border-gray-300 dark:bg-gray-900 dark:text-gray-400 dark:border-gray-700'
}

function lineClasses(idx: number, current: number): string {
  return idx < current ? 'bg-emerald-500' : 'bg-gray-300 dark:bg-gray-700'
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
  // M5.B manual-override path: the EEAT gate skill #11 lands in M7. We let
  // the user hit `mark_eeat_passed` directly with run_id=0 + the article's
  // current eeat criteria version. The skill flow will use a real run id
  // wired from procedure 4.
  await runVerb('mark EEAT passed', () =>
    articlesStore.markEeatPassed(articleId.value, {
      expected_etag: article.value!.step_etag!,
      run_id: 0,
      eeat_criteria_version: article.value!.eeat_criteria_version_used ?? 1,
    }),
  )
}

async function actionMarkPublished(): Promise<void> {
  if (!article.value?.step_etag) return
  await runVerb('publish', () =>
    articlesStore.markPublished(articleId.value, {
      expected_etag: article.value!.step_etag!,
      run_id: 0,
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
  <div class="mx-auto max-w-7xl">
    <nav
      aria-label="Breadcrumb"
      class="mb-2 text-sm text-gray-600 dark:text-gray-400"
    >
      <ol class="flex flex-wrap items-center gap-1">
        <li>
          <RouterLink
            :to="`/projects/${projectId}/overview`"
            class="hover:underline"
          >
            {{ project?.name ?? 'Project' }}
          </RouterLink>
        </li>
        <li
          aria-hidden="true"
          class="text-gray-400"
        >
          /
        </li>
        <li>
          <RouterLink
            :to="`/projects/${projectId}/articles`"
            class="hover:underline"
          >
            Articles
          </RouterLink>
        </li>
        <li
          aria-hidden="true"
          class="text-gray-400"
        >
          /
        </li>
        <li
          class="truncate"
          aria-current="page"
        >
          {{ article?.title ?? '…' }}
        </li>
      </ol>
    </nav>

    <header class="mb-4">
      <div class="flex flex-wrap items-baseline gap-3">
        <h1 class="text-2xl font-bold tracking-tight">
          {{ article?.title ?? 'Loading…' }}
        </h1>
        <StatusBadge
          v-if="article"
          :status="article.status"
          kind="article"
        />
        <span
          v-if="article"
          class="rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-700 dark:bg-gray-800 dark:text-gray-300"
        >
          v{{ article.version }}
        </span>
      </div>
      <p
        v-if="article"
        class="mt-1 text-sm text-gray-600 dark:text-gray-400"
      >
        <span class="font-mono">{{ article.slug }}</span>
        <template v-if="author">
          · author <strong>{{ author.name }}</strong>
        </template>
        <template v-if="reviewer">
          · reviewer <strong>{{ reviewer.name }}</strong>
        </template>
      </p>
    </header>

    <ol
      v-if="article"
      class="mb-4 flex items-center gap-2 overflow-x-auto pb-1"
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
          <span class="mt-1 whitespace-nowrap text-[11px] text-gray-600 dark:text-gray-400">
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
      class="mb-4 flex flex-wrap items-center gap-2"
    >
      <button
        v-if="article.status === 'briefing'"
        type="button"
        class="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
        @click="gotoTab('brief')"
      >
        Edit brief
      </button>

      <button
        v-if="article.status === 'outlined'"
        type="button"
        class="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
        @click="gotoTab('draft')"
      >
        Continue to draft
      </button>

      <button
        v-if="article.status === 'outlined'"
        type="button"
        class="rounded border border-emerald-300 bg-emerald-50 px-3 py-1.5 text-sm font-medium text-emerald-800 hover:bg-emerald-100 disabled:opacity-50 dark:border-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-200"
        :disabled="actionBusy !== null"
        @click="actionMarkDrafted"
      >
        {{ actionBusy === 'mark drafted' ? 'Marking…' : 'Mark drafted' }}
      </button>

      <button
        v-if="article.status === 'drafted'"
        type="button"
        class="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
        @click="gotoTab('edited')"
      >
        Continue to editor
      </button>

      <button
        v-if="article.status === 'edited'"
        type="button"
        class="rounded border border-purple-300 bg-purple-50 px-3 py-1.5 text-sm font-medium text-purple-800 hover:bg-purple-100 disabled:opacity-50 dark:border-purple-700 dark:bg-purple-900/40 dark:text-purple-200"
        :disabled="actionBusy !== null"
        @click="actionMarkEeatPassed"
      >
        {{ actionBusy === 'mark EEAT passed' ? 'Marking…' : 'Mark EEAT passed (manual)' }}
      </button>

      <button
        v-if="article.status === 'eeat_passed'"
        type="button"
        class="rounded bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
        :disabled="actionBusy !== null"
        @click="actionMarkPublished"
      >
        {{ actionBusy === 'publish' ? 'Publishing…' : 'Publish' }}
      </button>

      <button
        v-if="article.status === 'published'"
        type="button"
        class="rounded border border-orange-300 bg-orange-50 px-3 py-1.5 text-sm font-medium text-orange-800 hover:bg-orange-100 disabled:opacity-50 dark:border-orange-700 dark:bg-orange-900/40 dark:text-orange-200"
        :disabled="actionBusy !== null"
        @click="actionMarkRefreshDue"
      >
        Mark refresh due
      </button>

      <button
        type="button"
        class="rounded border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-100 disabled:opacity-50 dark:border-gray-700 dark:hover:bg-gray-800"
        :disabled="actionBusy !== null"
        @click="actionCreateVersion"
      >
        New version
      </button>
    </div>

    <p
      v-if="!article && !loadingArticle"
      class="rounded border border-dashed border-gray-300 p-4 text-sm text-gray-600 dark:border-gray-700 dark:text-gray-300"
    >
      Article not found.
    </p>

    <p
      v-else-if="loadingArticle && !article"
      class="rounded border border-dashed border-gray-300 p-4 text-sm text-gray-600 dark:border-gray-700 dark:text-gray-300"
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
        class="mt-4"
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
      class="mt-3 text-xs text-gray-500 dark:text-gray-400"
    >
      Article is in <code>briefing</code>. Save the brief to advance the
      timeline.
    </p>
  </div>
</template>
