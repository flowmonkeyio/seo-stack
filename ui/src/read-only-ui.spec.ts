import { describe, expect, it } from 'vitest'
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = dirname(fileURLToPath(import.meta.url))
const SCOPES = ['components', 'lib', 'stores', 'views']
const WRITE_PATTERNS = [
  /\bapiWrite\b/,
  /method:\s*['"`](POST|PATCH|PUT|DELETE)['"`]/,
]

function filesUnder(dir: string): string[] {
  const out: string[] = []
  for (const entry of readdirSync(dir)) {
    const path = join(dir, entry)
    const stat = statSync(path)
    if (stat.isDirectory()) out.push(...filesUnder(path))
    else if (/\.(ts|vue)$/.test(entry) && !entry.endsWith('.spec.ts')) out.push(path)
  }
  return out
}

describe('read-only UI contract', () => {
  it('keeps product views and stores free of write calls', () => {
    const offenders: string[] = []
    for (const scope of SCOPES) {
      for (const file of filesUnder(join(ROOT, scope))) {
        const text = readFileSync(file, 'utf8')
        if (WRITE_PATTERNS.some((pattern) => pattern.test(text))) offenders.push(file)
      }
    }
    expect(offenders).toEqual([])
  })
})
