<script setup lang="ts">
import { ref } from 'vue'

import StatusBadge from '@/components/StatusBadge.vue'
import {
  ArticleActionBar,
  ArticleAssetCard,
  ArticleStatusStepper,
  BudgetMeter,
  ComplianceRuleRow,
  CredentialHealthBadge,
  DriftBaselineCard,
  EeatCriterionRow,
  EeatScoreCard,
  GscOpportunityCard,
  IntegrationProviderCard,
  IntegrationSetupDialog,
  LinkSuggestionCard,
  MarkdownSectionEditor,
  ProcedureCard,
  ProjectHeader,
  ProjectStatusSummary,
  PublishingTargetCard,
  RunStepAccordion,
  RunTimeline,
  ScheduleRuleCard,
  SchemaEditorPanel,
  SourceLedger,
} from '@/components/domain'
import {
  UiBadge,
  UiBulkActionBar,
  UiBreadcrumbs,
  UiButton,
  UiButtonGroup,
  UiCallout,
  UiCard,
  UiCheckbox,
  UiCodeBlock,
  UiConfirmDialog,
  UiDescriptionList,
  UiDiffBlock,
  UiDropdownMenu,
  UiEmptyState,
  UiFilterBar,
  UiFormField,
  UiIconButton,
  UiInput,
  UiJsonBlock,
  UiLoadingState,
  UiPageHeader,
  UiPageShell,
  UiPanel,
  UiPopover,
  UiProgressBar,
  UiRadioGroup,
  UiRange,
  UiScoreMeter,
  UiSecretInput,
  UiSectionHeader,
  UiSelect,
  UiSidePanel,
  UiSkeleton,
  UiSwitch,
  UiTextarea,
  UiToast,
  UiToolbar,
  UiTooltip,
} from '@/components/ui'

const sidePanelOpen = ref(false)
const confirmOpen = ref(false)
const integrationDialogOpen = ref(false)
const checkboxValue = ref(true)
const switchValue = ref(true)
const rangeValue = ref(72)
const radioValue = ref('api')
const selectValue = ref('articles')
const search = ref('refresh')
const textValue = ref('Internal linking opportunities')
const textAreaValue = ref('## What changed\n\n- Added semantic tokens\n- Normalized status rendering\n')
const secretValue = ref('sk-content-stack-demo-token')
const markdownValue = ref('## Bonus terms to compare\n\nUse wagering requirement, withdrawal time, and provider reputation as the main comparison axes.')

const statusSamples = [
  ['topic', 'approved'],
  ['article', 'eeat_passed'],
  ['run', 'running'],
  ['procedure', 'failed'],
  ['interlink', 'suggested'],
  ['publish', 'published'],
  ['project', 'active'],
  ['integration', 'degraded'],
  ['drift', 'high'],
  ['eeat', 'passing'],
  ['budget', 'approaching'],
] as const

const dropdownItems = [
  { key: 'group', as: 'header' as const, label: 'Article actions' },
  { key: 'refresh', label: 'Refresh article', shortcut: 'R' },
  { key: 'publish', label: 'Publish now', shortcut: 'P' },
  { key: 'sep', as: 'separator' as const },
  { key: 'archive', label: 'Archive', tone: 'danger' as const },
]

const projectMetrics = [
  { label: 'Articles', value: 128, delta: '+12', deltaTone: 'positive' as const },
  { label: 'Refresh due', value: 9, delta: '+3', deltaTone: 'negative' as const },
  { label: 'Open runs', value: 4, delta: 'stable', deltaTone: 'neutral' as const },
  { label: 'Indexed', value: '91%', delta: '+4%', deltaTone: 'positive' as const },
]

const runSteps = [
  { id: 'brief', label: 'Content brief', status: 'succeeded' as const, detail: 'SERP evidence merged', durationMs: 940 },
  { id: 'draft', label: 'Draft body', status: 'running' as const, detail: 'Writing section 3 of 7', progress: 62 },
  { id: 'publish', label: 'Publish', status: 'pending' as const, detail: 'Waiting on editor and EEAT gates' },
]

const runAccordionSteps = [
  {
    id: 'keyword-discovery',
    label: 'Keyword discovery',
    status: 'success',
    duration: '4.2s',
    output: { queued_topics: 18, rejected: 3, source: 'dataforseo-mock' },
    log: 'Fetched seed terms\nMerged SERP overlap\nQueued 18 topics',
  },
  {
    id: 'publish',
    label: 'Publish to target',
    status: 'pending',
    duration: null,
    output: { target: 'wordpress-primary', blocked_by: 'eeat_gate' },
  },
]

const sourceItems = [
  {
    id: 1,
    title: 'Search quality evaluator guidelines',
    publisher: 'Google Search Central',
    url: 'https://developers.google.com/search',
    cited: true,
    notes: 'Used for EEAT quality requirements.',
  },
  {
    id: 2,
    title: 'Provider review archive',
    publisher: 'Project crawl',
    url: '/reviews/providers',
    cited: false,
  },
]

const diffLines = [
  { kind: 'meta' as const, text: '@@ schema headline @@' },
  { kind: 'remove' as const, oldNumber: 12, text: '"headline": "Best Casinos"' },
  { kind: 'add' as const, newNumber: 12, text: '"headline": "Best Fast Withdrawal Casinos"' },
  { kind: 'context' as const, oldNumber: 13, newNumber: 13, text: '"dateModified": "2026-05-10"' },
]
</script>

<template>
  <UiPageShell
    spacing="lg"
    padded-bottom
  >
    <UiPageHeader
      title="Operations Console Design System"
      eyebrow="Developer surface"
      description="Semantic tokens, primitives, domain components, and state mappings used across the content-stack UI."
    >
      <template #breadcrumbs>
        <UiBreadcrumbs :items="[{ label: 'Design system' }]" />
      </template>
      <template #actions>
        <UiButton
          variant="secondary"
          @click="sidePanelOpen = true"
        >
          Open panel
        </UiButton>
        <UiButton
          variant="primary"
          @click="integrationDialogOpen = true"
        >
          Configure integration
        </UiButton>
      </template>
    </UiPageHeader>

    <section class="space-y-3">
      <UiSectionHeader
        title="Tokens and Status"
        description="The semantic layer is the thing the rest of the UI consumes."
      />
      <div class="grid gap-3 lg:grid-cols-[1fr_2fr]">
        <div class="grid grid-cols-2 gap-2 rounded-md border border-default bg-bg-surface p-3">
          <div class="rounded-sm border border-subtle bg-bg-app p-3 text-sm text-fg-muted">
            bg.app
          </div>
          <div class="rounded-sm border border-subtle bg-bg-surface p-3 text-sm text-fg-muted">
            bg.surface
          </div>
          <div class="rounded-sm border border-subtle bg-bg-surface-alt p-3 text-sm text-fg-muted">
            surface alt
          </div>
          <div class="rounded-sm border border-subtle bg-bg-sunken p-3 text-sm text-fg-muted">
            sunken
          </div>
          <div class="rounded-sm bg-accent p-3 text-sm text-fg-on-accent">
            accent
          </div>
          <div class="rounded-sm bg-eeat p-3 text-sm text-fg-on-accent">
            eeat
          </div>
        </div>
        <div class="flex flex-wrap gap-2 rounded-md border border-default bg-bg-surface p-3">
          <StatusBadge
            v-for="[domain, status] in statusSamples"
            :key="`${domain}:${status}`"
            :domain="domain"
            :status="status"
          />
        </div>
      </div>
    </section>

    <section class="space-y-3">
      <UiSectionHeader
        title="Core Primitives"
        description="Buttons, form controls, status, feedback, overlays, and utility surfaces."
      />
      <div class="grid items-start gap-4 xl:grid-cols-3">
        <UiCard density="compact">
          <template #header>
            <h2 class="text-sm font-semibold text-fg-strong">
              Actions
            </h2>
            <UiBadge tone="info">
              buttons
            </UiBadge>
          </template>
          <div class="space-y-3">
            <div class="flex flex-wrap gap-2">
              <UiButton variant="primary">
                Primary
              </UiButton>
              <UiButton>Secondary</UiButton>
              <UiButton variant="ghost">
                Ghost
              </UiButton>
              <UiButton variant="danger">
                Danger
              </UiButton>
              <UiButton
                variant="secondary"
                loading
              >
                Saving
              </UiButton>
            </div>
            <UiToolbar aria-label="Toolbar demo">
              <UiIconButton aria-label="Undo">
                ↶
              </UiIconButton>
              <UiIconButton aria-label="Redo">
                ↷
              </UiIconButton>
              <UiButtonGroup aria-label="Segmented mode">
                <UiButton
                  size="sm"
                  variant="primary"
                >
                  Draft
                </UiButton>
                <UiButton size="sm">
                  Edited
                </UiButton>
              </UiButtonGroup>
              <template #right>
                <UiDropdownMenu
                  :items="dropdownItems"
                  placement="bottom-end"
                  @select="() => undefined"
                >
                  <template #trigger="{ toggle }">
                    <UiButton
                      data-dropdown-trigger
                      size="sm"
                      @click="toggle"
                    >
                      More
                    </UiButton>
                  </template>
                </UiDropdownMenu>
              </template>
            </UiToolbar>
            <UiBulkActionBar
              :count="3"
              :total="42"
              selectable-all
            >
              <UiButton size="sm">
                Approve
              </UiButton>
              <UiButton
                size="sm"
                variant="danger"
              >
                Reject
              </UiButton>
            </UiBulkActionBar>
          </div>
        </UiCard>

        <UiCard density="compact">
          <template #header>
            <h2 class="text-sm font-semibold text-fg-strong">
              Forms
            </h2>
            <UiBadge tone="success">
              inputs
            </UiBadge>
          </template>
          <div class="space-y-3">
            <UiFormField
              label="Topic"
              help="Use the reader-facing article idea."
            >
              <UiInput
                v-model="textValue"
                placeholder="Article topic"
              />
            </UiFormField>
            <UiFormField label="Content type">
              <UiSelect
                v-model="selectValue"
                :options="[
                  { value: 'articles', label: 'Articles' },
                  { value: 'refresh', label: 'Refresh candidates' },
                  { value: 'links', label: 'Internal links' },
                ]"
              />
            </UiFormField>
            <UiFormField label="Secret">
              <UiSecretInput v-model="secretValue" />
            </UiFormField>
            <UiCheckbox
              v-model="checkboxValue"
              label="Require human approval before publish"
              description="The agent can prepare the publish, but cannot ship until approved."
            />
            <UiSwitch
              v-model="switchValue"
              aria-label="Enable drift watch"
            />
            <UiRadioGroup
              v-model="radioValue"
              name="design-auth-mode"
              orientation="horizontal"
              :options="[
                { value: 'api', label: 'API' },
                { value: 'local', label: 'Local' },
              ]"
            />
            <UiRange
              v-model="rangeValue"
              aria-label="Confidence floor"
              :format="(v) => `${v}%`"
            />
            <UiTextarea
              v-model="textAreaValue"
              :rows="4"
            />
          </div>
        </UiCard>

        <UiCard density="compact">
          <template #header>
            <h2 class="text-sm font-semibold text-fg-strong">
              Feedback
            </h2>
            <UiBadge tone="warning">
              states
            </UiBadge>
          </template>
          <div class="space-y-3">
            <UiCallout
              tone="warning"
              title="Vendor credentials needed"
            >
              Connect GSC before running crawl-error-watch.
            </UiCallout>
            <UiFilterBar
              v-model:search="search"
              :active="[{ key: 'status', label: 'Status', value: 'Refresh due' }]"
              search-placeholder="Search articles"
            >
              <UiButton size="sm">
                Filter
              </UiButton>
            </UiFilterBar>
            <UiProgressBar
              :value="62"
              show-label
            />
            <div class="flex items-center gap-4">
              <UiScoreMeter
                :value="84"
                tone="eeat"
              />
              <UiLoadingState
                label="Checking schema"
                inline
              />
              <UiSkeleton
                width="8rem"
                height="1rem"
              />
            </div>
            <UiToast
              tone="success"
              title="Integration saved"
              description="Agents can now use the WordPress target."
              action-label="View"
            />
            <UiPopover
              width="260px"
              aria-label="Popover demo"
            >
              <template #trigger="{ toggle }">
                <UiButton
                  data-popover-trigger
                  size="sm"
                  @click="toggle"
                >
                  Open popover
                </UiButton>
              </template>
              <div class="space-y-2 p-3">
                <p class="text-sm font-medium text-fg-strong">
                  Run controls
                </p>
                <p class="text-xs text-fg-muted">
                  Popover content can hold short interactive forms.
                </p>
              </div>
            </UiPopover>
            <UiTooltip content="Tooltips explain icon-only actions.">
              <UiIconButton aria-label="Tooltip sample">
                ?
              </UiIconButton>
            </UiTooltip>
          </div>
        </UiCard>
      </div>
    </section>

    <section class="space-y-3">
      <UiSectionHeader
        title="Developer Utilities"
        description="Code, JSON, diffs, empty states, panels, and metadata blocks."
      />
      <div class="grid items-start gap-4 lg:grid-cols-2">
        <div class="space-y-3">
          <UiCodeBlock
            language="bash"
            code="content-stack run new-content --project askmrgambler"
            copyable
          />
          <UiJsonBlock
            :data="{ procedure: 'new-content', status: 'running', article_id: 42 }"
            copyable
          />
          <UiDiffBlock
            filename="schema.json"
            :lines="diffLines"
            wrap
          />
        </div>
        <div class="space-y-3">
          <UiPanel>
            <UiDescriptionList
              layout="grid"
              :columns="2"
              :items="[
                { label: 'Project', value: 'askmrgambler' },
                { label: 'Primary target', value: 'wordpress-primary' },
                { label: 'Run token', value: 'run_demo_123', mono: true },
                { label: 'Mode', value: 'agent-managed' },
              ]"
            />
          </UiPanel>
          <UiEmptyState
            title="No queued topics"
            description="Start discovery or import a competitor sitemap to seed the backlog."
            size="sm"
          >
            <template #actions>
              <UiButton
                size="sm"
                variant="primary"
              >
                Discover topics
              </UiButton>
            </template>
          </UiEmptyState>
          <UiButton
            variant="danger"
            @click="confirmOpen = true"
          >
            Open confirm dialog
          </UiButton>
        </div>
      </div>
    </section>

    <section class="space-y-3">
      <UiSectionHeader
        title="Project Components"
        description="Reusable content-stack operations components with no store coupling."
      />
      <ProjectHeader
        name="askmrgambler"
        slug="askmrgambler"
        description="Affiliate content operations with local project context and daemon-owned credentials."
        state="active"
      />
      <ProjectStatusSummary :metrics="projectMetrics" />
      <div class="grid items-start gap-4 lg:grid-cols-3">
        <IntegrationProviderCard
          provider="Google Search Console"
          description="Indexing, query, and inspection data."
          health="healthy"
          connected
        />
        <PublishingTargetCard
          name="Primary WordPress"
          kind="wordpress"
          status="published"
          url="https://example.com"
          primary
          last-published-at="2026-05-10 10:42"
        />
        <BudgetMeter
          :spent="184"
          :cap="400"
          period="May"
        />
      </div>
    </section>

    <section class="space-y-3">
      <UiSectionHeader
        title="Article Production"
        description="The writing, source, asset, schema, quality, and publish path."
      />
      <ArticleStatusStepper current="edited" />
      <div class="grid items-start gap-4 lg:grid-cols-3">
        <EeatScoreCard
          :score="87"
          verdict="passing"
          :breakdown="[
            { label: 'Experience', value: 82 },
            { label: 'Expertise', value: 88 },
            { label: 'Trust', value: 91 },
          ]"
        />
        <ArticleAssetCard
          kind="hero"
          alt-text="Comparison table showing casino withdrawal speeds by provider"
          :width="1600"
          :height="900"
          :bytes="184000"
        />
        <SchemaEditorPanel
          schema-type="Article"
          schema-json="{&quot;@context&quot;:&quot;https://schema.org&quot;,&quot;@type&quot;:&quot;Article&quot;,&quot;headline&quot;:&quot;Fast withdrawal casinos&quot;}"
          valid
        />
      </div>
      <div class="grid items-start gap-4 lg:grid-cols-2">
        <SourceLedger :items="sourceItems" />
        <MarkdownSectionEditor
          v-model="markdownValue"
          title="Comparison Criteria"
          section-key="criteria"
          dirty
        />
      </div>
      <ArticleActionBar
        dirty
        can-publish
        can-refresh
      />
    </section>

    <section class="space-y-3">
      <UiSectionHeader
        title="Runs and Ongoing Ops"
        description="Procedures, schedules, linking, GSC opportunities, crawl drift, and gates."
      />
      <div class="grid items-start gap-4 lg:grid-cols-3">
        <ProcedureCard
          name="New Content"
          slug="new-content"
          description="Discover, brief, draft, edit, gate, schema, assets, and publish."
          status="enabled"
          last-run-at="2026-05-10 09:41"
        />
        <ScheduleRuleCard
          name="Weekly refresh detector"
          cron="0 8 * * 1"
          status="enabled"
          next-run-at="2026-05-11 08:00"
          :concurrency-limit="1"
        />
        <GscOpportunityCard
          query="best fast payout casino"
          url="/best-fast-payout-casinos"
          :clicks="121"
          :impressions="8400"
          :ctr="0.014"
          :position="7.8"
          opportunity="striking-distance"
        />
      </div>
      <div class="grid items-start gap-4 lg:grid-cols-2">
        <div class="rounded-md border border-default bg-bg-surface">
          <RunTimeline :steps="runSteps" />
        </div>
        <RunStepAccordion
          :steps="runAccordionSteps"
          initially-open="keyword-discovery"
        />
      </div>
      <div class="grid items-start gap-4 lg:grid-cols-3">
        <LinkSuggestionCard
          from-title="Casino bonus wagering guide"
          to-title="Fast withdrawal casinos"
          anchor="fast payout casino"
          status="suggested"
          :score="0.82"
          reason="Anchor is semantically close and target page is under-linked."
        />
        <DriftBaselineCard
          title="Fast withdrawal casinos"
          severity="medium"
          :score="0.41"
          checked-at="2026-05-10 10:05"
          :changed-fields="['meta description', 'schema headline']"
        />
        <div class="space-y-3">
          <ComplianceRuleRow
            name="No bonus claims without source"
            kind="editorial"
            position="pre-publish"
            required
            active
            last-checked-at="today"
          />
          <EeatCriterionRow
            criterion-id="eeat-trust-01"
            label="Clear ownership and contact context"
            category="Trust"
            verdict="passing"
            required
          />
          <CredentialHealthBadge status="expiring" />
        </div>
      </div>
    </section>

    <IntegrationSetupDialog
      v-model="integrationDialogOpen"
      provider-name="WordPress"
      provider-slug="wordpress-primary"
      description="Connect the publishing target once; agents can then publish without project env files."
      health="degraded"
      auth-mode="apiKey"
      connection-name="Primary WordPress"
      endpoint-url="https://example.com/wp-json"
      credential-value="wp-demo-secret"
      dirty
    />

    <UiSidePanel
      v-model="sidePanelOpen"
      title="Side panel"
      description="Use for row detail and setup flows."
    >
      <p class="text-sm text-fg-muted">
        Side panels keep detail work in context without creating another route.
      </p>
      <template #footer>
        <UiButton @click="sidePanelOpen = false">
          Close
        </UiButton>
      </template>
    </UiSidePanel>

    <UiConfirmDialog
      v-model="confirmOpen"
      title="Archive topic?"
      description="This keeps history but removes the topic from active queues."
      confirm-label="Archive"
      tone="danger"
    />
  </UiPageShell>
</template>
