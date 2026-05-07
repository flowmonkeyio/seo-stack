import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import StatusBadge from './StatusBadge.vue'

describe('StatusBadge', () => {
  it('renders the status label', () => {
    const w = mount(StatusBadge, { props: { status: 'success', kind: 'run' } })
    expect(w.text()).toBe('success')
    expect(w.attributes('data-status')).toBe('success')
    expect(w.attributes('data-kind')).toBe('run')
  })

  it('uses the topic palette for topic statuses', () => {
    const w = mount(StatusBadge, { props: { status: 'queued', kind: 'topic' } })
    expect(w.classes().some((c) => c.includes('bg-gray-100'))).toBe(true)
  })

  it('uses the article palette for article statuses', () => {
    const w = mount(StatusBadge, { props: { status: 'published', kind: 'article' } })
    expect(w.classes().some((c) => c.includes('bg-emerald-100'))).toBe(true)
  })

  it('uses the run palette for run statuses', () => {
    const w = mount(StatusBadge, { props: { status: 'failed', kind: 'run' } })
    expect(w.classes().some((c) => c.includes('bg-red-100'))).toBe(true)
  })

  it('uses the interlink palette for interlink statuses', () => {
    const w = mount(StatusBadge, { props: { status: 'broken', kind: 'interlink' } })
    expect(w.classes().some((c) => c.includes('bg-red-100'))).toBe(true)
  })

  it('falls back to neutral grey for unknown statuses', () => {
    const w = mount(StatusBadge, { props: { status: 'made-up', kind: 'topic' } })
    expect(w.classes().some((c) => c.includes('bg-gray-100'))).toBe(true)
  })

  it('applies the small variant when prop is set', () => {
    const w = mount(StatusBadge, {
      props: { status: 'success', kind: 'run', small: true },
    })
    expect(w.classes().some((c) => c.includes('text-[10px]'))).toBe(true)
  })

  it('renders a custom label via the default slot', () => {
    const w = mount(StatusBadge, {
      props: { status: 'active', kind: 'project' },
      slots: { default: 'live' },
    })
    expect(w.text()).toBe('live')
  })
})
