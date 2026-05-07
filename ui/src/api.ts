// STUB — replaced in M3 by the auto-generated FastAPI OpenAPI types.
//
// Generated from FastAPI OpenAPI via:
//   npx openapi-typescript http://127.0.0.1:5180/openapi.json -o src/api.ts
//
// DO NOT EDIT BY HAND. Regenerate after any FastAPI route change.
// Until M3 lands the REST surface there is no OpenAPI spec to pull from,
// so this file only re-exports a placeholder type that the M0 HomeView uses.

export type HealthResponse = {
  status: string
  version?: string
  uptime_s?: number
  milestone?: string
  db_status?: string
  scheduler_running?: boolean
  // M0 daemon may return additional fields; we display the raw JSON anyway.
  [key: string]: unknown
}
