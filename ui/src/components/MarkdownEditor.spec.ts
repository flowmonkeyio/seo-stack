import { describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

import MarkdownEditor from './MarkdownEditor.vue'

describe('MarkdownEditor', () => {
  it('emits update:value when typed into', async () => {
    const w = mount(MarkdownEditor, {
      props: { value: 'hello', autoSaveMs: 0 },
    })
    const ta = w.find('textarea')
    await ta.setValue('hello world')
    const events = w.emitted('update:value') ?? []
    expect(events.length).toBeGreaterThanOrEqual(1)
    expect(events[events.length - 1][0]).toBe('hello world')
  })

  it('shows a word + character count footer', () => {
    const w = mount(MarkdownEditor, {
      props: { value: 'one two three', autoSaveMs: 0 },
    })
    expect(w.text()).toContain('3 words')
    expect(w.text()).toContain('13 chars')
  })

  it('calls onSave when the manual button is clicked, passing the ifMatch token', async () => {
    const onSave = vi.fn().mockResolvedValue({ updated_at: '2026-01-01T00:00:00Z' })
    const w = mount(MarkdownEditor, {
      props: {
        value: 'first',
        updatedAt: '2025-12-31T00:00:00Z',
        onSave,
        autoSaveMs: 0,
      },
    })
    await w.find('textarea').setValue('first edit')
    const saveBtn = w.findAll('button').find((b) => b.text().includes('Save'))!
    expect(saveBtn).toBeTruthy()
    await saveBtn.trigger('click')
    await flushPromises()
    expect(onSave).toHaveBeenCalledTimes(1)
    expect(onSave.mock.calls[0][0]).toBe('first edit')
    expect(onSave.mock.calls[0][1]).toBe('2025-12-31T00:00:00Z')
  })

  it('debounces auto-save and fires once after autoSaveMs', async () => {
    vi.useFakeTimers()
    const onSave = vi.fn().mockResolvedValue({ updated_at: '2026-01-02T00:00:00Z' })
    const w = mount(MarkdownEditor, {
      props: {
        value: 'a',
        updatedAt: '2026-01-01T00:00:00Z',
        onSave,
        autoSaveMs: 5_000,
      },
    })
    await w.find('textarea').setValue('a1')
    await w.find('textarea').setValue('a2')
    await w.find('textarea').setValue('a3')
    expect(onSave).not.toHaveBeenCalled()
    vi.advanceTimersByTime(5_000)
    await flushPromises()
    expect(onSave).toHaveBeenCalledTimes(1)
    expect(onSave.mock.calls[0][0]).toBe('a3')
    vi.useRealTimers()
  })

  it('shows the conflict prompt when onSave throws a 412 error', async () => {
    const err = Object.assign(new Error('precondition failed'), {
      status: 412,
      body: { current_md: 'remote text' },
    })
    const onSave = vi.fn().mockRejectedValue(err)
    const w = mount(MarkdownEditor, {
      props: {
        value: 'first',
        updatedAt: '2025-12-31T00:00:00Z',
        onSave,
        autoSaveMs: 0,
      },
    })
    await w.find('textarea').setValue('first edit')
    const saveBtn = w.findAll('button').find((b) => b.text().includes('Save'))!
    await saveBtn.trigger('click')
    await flushPromises()
    expect(w.text()).toContain('Remote copy changed')
    expect(w.text()).toContain('Reload remote')
    expect(w.text()).toContain('Overwrite')
  })
})
