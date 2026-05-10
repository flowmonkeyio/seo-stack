<script setup lang="ts">
import { computed } from 'vue'

import CredentialHealthBadge from './CredentialHealthBadge.vue'
import UiButton from '../ui/UiButton.vue'
import UiCallout from '../ui/UiCallout.vue'
import UiDialog from '../ui/UiDialog.vue'
import UiFormField from '../ui/UiFormField.vue'
import UiInput from '../ui/UiInput.vue'
import UiRadioGroup from '../ui/UiRadioGroup.vue'
import UiSecretInput from '../ui/UiSecretInput.vue'

type AuthMode = 'oauth' | 'apiKey' | 'basic' | 'local'

const props = withDefaults(
  defineProps<{
    modelValue: boolean
    providerName: string
    providerSlug?: string
    description?: string | null
    health?: 'healthy' | 'degraded' | 'failing' | 'notConnected' | 'expiring' | 'expired'
    authMode?: AuthMode
    connectionName?: string
    endpointUrl?: string
    credentialValue?: string
    setupUrl?: string | null
    dirty?: boolean
    saving?: boolean
    testing?: boolean
    disconnecting?: boolean
    error?: string | null
  }>(),
  {
    providerSlug: undefined,
    description: null,
    authMode: 'apiKey',
    health: 'notConnected',
    connectionName: '',
    endpointUrl: '',
    credentialValue: '',
    setupUrl: null,
    dirty: false,
    saving: false,
    testing: false,
    disconnecting: false,
    error: null,
  },
)

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'update:authMode', value: AuthMode): void
  (e: 'update:connectionName', value: string): void
  (e: 'update:endpointUrl', value: string): void
  (e: 'update:credentialValue', value: string): void
  (e: 'save'): void
  (e: 'test'): void
  (e: 'disconnect'): void
  (e: 'openSetupUrl'): void
}>()

const dialogTitle = computed(() => `Connect ${props.providerName}`)

const authOptions = [
  {
    value: 'oauth',
    label: 'OAuth',
    description: 'Open the provider consent flow, then store the granted token in the daemon.',
  },
  {
    value: 'apiKey',
    label: 'API key',
    description: 'Store a provider token, password, or secret in the daemon credential vault.',
  },
  {
    value: 'basic',
    label: 'Basic auth',
    description: 'Use username and password style credentials for legacy APIs.',
  },
  {
    value: 'local',
    label: 'Local project',
    description: 'Use a local repository path, admin API, or direct database adapter.',
  },
]

function updateOpen(value: boolean) {
  emit('update:modelValue', value)
}

function updateAuthMode(value: string | number) {
  emit('update:authMode', String(value) as AuthMode)
}
</script>

<template>
  <UiDialog
    :model-value="modelValue"
    :title="dialogTitle"
    :description="description ?? 'Configure credentials and connection settings for this provider.'"
    size="lg"
    scroll-body
    :static-backdrop="dirty"
    :no-escape="dirty"
    @update:model-value="updateOpen"
  >
    <div class="space-y-4">
      <UiCallout
        v-if="dirty"
        tone="warning"
        density="compact"
        title="Unsaved changes"
      >
        Save or discard this connection before closing the dialog.
      </UiCallout>

      <UiCallout
        v-if="error"
        tone="danger"
        density="compact"
        title="Connection failed"
      >
        {{ error }}
      </UiCallout>

      <div class="flex flex-wrap items-center gap-3 rounded-md border border-subtle bg-bg-surface-alt p-3">
        <div class="min-w-0 flex-1">
          <p class="text-sm font-semibold text-fg-strong">
            {{ providerName }}
          </p>
          <p
            v-if="providerSlug"
            class="font-mono text-xs text-fg-muted"
          >
            {{ providerSlug }}
          </p>
        </div>
        <CredentialHealthBadge :status="health" />
      </div>

      <slot name="summary" />

      <UiFormField
        label="Authentication method"
        help="The daemon owns credentials; site repositories should not need local env files for provider keys."
      >
        <UiRadioGroup
          name="integration-auth-mode"
          :model-value="authMode"
          :options="authOptions"
          variant="card"
          @update:model-value="updateAuthMode"
        />
      </UiFormField>

      <div class="grid gap-3 md:grid-cols-2">
        <UiFormField
          label="Connection name"
          help="A human-readable label shown to agents and operators."
        >
          <UiInput
            :model-value="connectionName"
            placeholder="Primary WordPress"
            @update:model-value="$emit('update:connectionName', String($event ?? ''))"
          />
        </UiFormField>

        <UiFormField
          label="Endpoint or project path"
          help="Use a base URL, admin API URL, or local adapter path."
        >
          <UiInput
            :model-value="endpointUrl"
            placeholder="https://example.com/wp-json"
            @update:model-value="$emit('update:endpointUrl', String($event ?? ''))"
          />
        </UiFormField>
      </div>

      <UiFormField
        v-if="authMode !== 'oauth' && authMode !== 'local'"
        label="Credential"
        help="Stored by the daemon. The app only shows masked values after save."
      >
        <UiSecretInput
          :model-value="credentialValue"
          placeholder="Paste token, password, or secret"
          @update:model-value="$emit('update:credentialValue', $event)"
        />
      </UiFormField>

      <UiCallout
        v-if="authMode === 'oauth'"
        tone="info"
        density="compact"
        title="Provider sign-in"
      >
        OAuth providers should open from this dialog, return to the local daemon callback, then show
        credential health here.
        <template #actions>
          <UiButton
            size="sm"
            variant="primary"
            :href="setupUrl ?? undefined"
            @click="$emit('openSetupUrl')"
          >
            Open authorization
          </UiButton>
        </template>
      </UiCallout>

      <slot name="fields" />
    </div>

    <template #footer>
      <slot name="footer">
        <UiButton
          v-if="health !== 'notConnected'"
          size="sm"
          variant="danger"
          :loading="disconnecting"
          @click="$emit('disconnect')"
        >
          Disconnect
        </UiButton>
        <UiButton
          size="sm"
          variant="secondary"
          :loading="testing"
          @click="$emit('test')"
        >
          Test connection
        </UiButton>
        <UiButton
          size="sm"
          variant="primary"
          :loading="saving"
          @click="$emit('save')"
        >
          Save integration
        </UiButton>
      </slot>
    </template>
  </UiDialog>
</template>
