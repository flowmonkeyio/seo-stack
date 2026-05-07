import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import KvList from './KvList.vue'

describe('KvList', () => {
  it('renders dt/dd pairs in the order given', () => {
    const w = mount(KvList, {
      props: {
        items: [
          { key: 'a', label: 'Alpha', value: 1 },
          { key: 'b', label: 'Beta', value: 'two' },
          { key: 'c', label: 'Gamma', value: true },
        ],
      },
    })
    const dts = w.findAll('dt')
    const dds = w.findAll('dd')
    expect(dts.map((d) => d.text())).toEqual(['Alpha', 'Beta', 'Gamma'])
    expect(dds.map((d) => d.text())).toEqual(['1', 'two', 'true'])
  })

  it('renders a dash for null/undefined values', () => {
    const w = mount(KvList, {
      props: {
        items: [
          { key: 'a', label: 'Alpha', value: null },
          { key: 'b', label: 'Beta', value: undefined },
        ],
      },
    })
    const dds = w.findAll('dd')
    expect(dds.map((d) => d.text())).toEqual(['—', '—'])
  })

  it('JSON-stringifies object values', () => {
    const w = mount(KvList, {
      props: {
        items: [{ key: 'cfg', label: 'Config', value: { foo: 'bar' } }],
      },
    })
    expect(w.find('dd').text()).toBe('{"foo":"bar"}')
  })

  it('honours item slot overrides', () => {
    const w = mount(KvList, {
      props: { items: [{ key: 'flag', label: 'Flag', value: true }] },
      slots: {
        'item:flag': '<span class="custom">YES</span>',
      },
    })
    expect(w.html()).toContain('class="custom"')
    expect(w.find('.custom').text()).toBe('YES')
  })
})
