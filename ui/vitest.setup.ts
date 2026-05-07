// Polyfills + globals for the jsdom test environment.

import { afterEach } from 'vitest'

// jsdom 25 doesn't ship a `window.matchMedia` shim — Tailwind's dark-mode
// detection isn't actually used in tests but the App.vue mount path can
// touch localStorage; no polyfill needed for that.

afterEach(() => {
  // Reset any DOM state between tests (Vitest unmounts the test wrapper
  // already, but if anything leaked into <head>, scrub here).
  document.head.querySelectorAll('style[data-vitest]').forEach((el) => el.remove())
})
