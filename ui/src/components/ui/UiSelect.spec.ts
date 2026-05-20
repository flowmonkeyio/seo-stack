import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import UiFormField from './UiFormField.vue'
import UiSelect from './UiSelect.vue'

describe('UiSelect', () => {
  it('renders the selected label and emits update/change when an option is selected', async () => {
    const wrapper = mount(UiSelect, {
      props: {
        modelValue: 'plan',
        options: [
          { value: 'plan', label: 'Plan' },
          { value: 'write', label: 'Write' },
        ],
      },
      attachTo: document.body,
    })

    expect(wrapper.get('[role="combobox"]').text()).toContain('Plan')

    await wrapper.get('[role="combobox"]').trigger('click')
    await wrapper.findAll('[role="option"]')[1].trigger('click')

    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual(['write'])
    expect(wrapper.emitted('change')?.[0]).toEqual(['write'])
    wrapper.unmount()
  })

  it('supports keyboard open, movement, selection, and Escape close', async () => {
    const wrapper = mount(UiSelect, {
      props: {
        modelValue: 'a',
        options: [
          { value: 'a', label: 'A' },
          { value: 'b', label: 'B' },
          { value: 'c', label: 'C' },
        ],
      },
      attachTo: document.body,
    })
    const button = wrapper.get('[role="combobox"]')

    await button.trigger('keydown', { key: 'ArrowDown' })
    expect(button.attributes('aria-expanded')).toBe('true')
    await button.trigger('keydown', { key: 'ArrowDown' })
    await button.trigger('keydown', { key: 'Enter' })

    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual(['b'])

    await button.trigger('click')
    expect(button.attributes('aria-expanded')).toBe('true')
    await button.trigger('keydown', { key: 'Escape' })
    expect(button.attributes('aria-expanded')).toBe('false')
    wrapper.unmount()
  })

  it('uses the surrounding UiFormField id for label association', () => {
    const wrapper = mount({
      components: { UiFormField, UiSelect },
      template: `
        <UiFormField label="Stage">
          <UiSelect model-value="plan" :options="[{ value: 'plan', label: 'Plan' }]" />
        </UiFormField>
      `,
    })

    const labelFor = wrapper.get('label').attributes('for')
    expect(labelFor).toBeTruthy()
    expect(wrapper.get('[role="combobox"]').attributes('id')).toBe(labelFor)
  })
})
