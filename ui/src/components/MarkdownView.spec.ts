import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import MarkdownView from './MarkdownView.vue'

describe('MarkdownView', () => {
  it('renders bold, italic, and links', () => {
    const w = mount(MarkdownView, {
      props: { source: '**bold** _italic_ [link](https://example.com)' },
    })
    expect(w.html()).toContain('<strong>bold</strong>')
    expect(w.html()).toContain('<em>italic</em>')
    expect(w.html()).toContain('<a href="https://example.com">link</a>')
  })

  it('renders fenced code blocks', () => {
    const w = mount(MarkdownView, {
      props: { source: '```\nconst x = 1\n```' },
    })
    expect(w.html()).toContain('<pre>')
    expect(w.html()).toContain('const x = 1')
  })

  it('strips dangerous <script> tags via DOMPurify', () => {
    const w = mount(MarkdownView, {
      props: { source: 'safe <script>alert(1)</script> text' },
    })
    expect(w.html()).not.toContain('<script>')
    expect(w.html()).not.toContain('alert(1)')
  })

  it('rewrites [^id] citation markers into <sup><a>', () => {
    const w = mount(MarkdownView, {
      props: { source: 'See [^1] for details.' },
    })
    expect(w.html()).toContain('cs-citation')
    expect(w.html()).toContain('href="#cite-1"')
    expect(w.html()).toContain('data-citation-id="1"')
  })

  it('shows the empty-message slot for blank input', () => {
    const w = mount(MarkdownView, {
      props: { source: '   ', emptyMessage: 'nothing here' },
    })
    expect(w.text()).toContain('nothing here')
  })
})
