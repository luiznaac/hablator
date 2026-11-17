# Code map

Module → key files → seam index, plus the app entry points; seeded from the scaffold and re-authored as the project's modules grew.

## Modules

### `src/api/` — the wire layer
**Purpose**: the typed client, the TanStack Query hooks and the hand-maintained DTO mirror. Every backend call crosses here; a component never calls `fetch`.
**Files**: `src/api/client.ts`; `src/api/queries.ts`; `src/api/types.ts`
**Seam(s)**:
- **Wire contract** — `src/api/types.ts` is the hand-maintained mirror of the backend edge DTOs; a backend DTO change updates it in the same commit. It is synced by hand, not generated, so a shape mismatch is a bug in the mirror.
- **Data seam** — `src/api/client.ts` holds the `request` wrapper, `ApiError` (carrying the `{code, detail, errors?}` envelope) and the `api` object: health, notification create/history/detail, delivery retry, channel list/upsert/delete. `BASE` comes from `VITE_API_BASE` (default `/api`). `src/api/queries.ts` holds the hooks (`useHealth`, `useNotifications`, `useNotification`, `useChannels`, and the send/retry/save/disable mutations); history refetches on window focus, never by polling. A new call is a typed function in `client.ts`, a hook in `queries.ts`, then consumption from a panel — in that order.

### `src/pages/` — route-level screens
**Purpose**: one component per route, plus the console's route-level panels; this is where query hooks are consumed.
**Files**: `src/pages/Console.tsx`; `src/pages/console/SendPanel.tsx`; `src/pages/console/HistoryPanel.tsx`; `src/pages/console/HealthPanel.tsx`; `src/pages/console/ChannelsPanel.tsx`
**Seam(s)**: `Console.tsx` is the `/` route: the 12-column grid (send 3, history 5, health + channels 4) that stacks below `lg`. The four panels are the console's data seams: Send maps the form through `lib/compose.ts`, validates the obvious gaps and surfaces the API envelope inline; History owns filters/offset/expanded id, renders deliveries + attempts and gates Retry through `lib/history.ts`'s `canRetry`; Health renders `GET /health` with the last-checked time; Channels renders `GET /channels` and edits/disables through `PUT`/`DELETE`. A new screen is a page component added to the route table in `src/App.tsx`.

### `src/components/` — shared chrome and presentational atoms
**Purpose**: presentational components that take props/children and fetch nothing.
**Files**: `src/components/Layout.tsx`; `src/components/Panel.tsx`; `src/components/console/atoms.tsx`; `src/components/console/fields.tsx`
**Seam(s)**: `Layout` is the shell (one `<header>` plus `<Outlet />`) every nested route renders inside; `Panel` is the reference titled container. `console/atoms.tsx` owns the status/channel vocabulary (`StatusChip`, `StatusDot`, `ChannelTag`) and `console/fields.tsx` the form controls (`Field`, `TextInput`, `TextArea`, `ChannelToggle`, `Notice`). Adding data fetching or state here is the wrong seam — it belongs in a page or a hook.

### `src/lib/` — pure helpers
**Purpose**: framework-free logic — formatting, request building, query/pager/retry-gate math, value parsing, error rendering — the only Vitest-covered surface.
**Files**: `src/lib/format.ts`; `src/lib/format.test.ts`; `src/lib/compose.ts`; `src/lib/compose.test.ts`; `src/lib/history.ts`; `src/lib/history.test.ts`; `src/lib/values.ts`; `src/lib/values.test.ts`; `src/lib/errors.ts`; `src/lib/errors.test.ts`
**Seam(s)**: no React imports; each helper is a plain exported function and its sibling `*.test.ts` pins it. `format.ts` renders timestamps/relative time/status labels and the presence-only channel-config summary (a secret-shaped key never renders its value); `compose.ts` validates the obvious form gaps and maps the send form to `NotificationRequestDTO`; `history.ts` builds the history query string, the offset pager math and the retriable-failure gate; `values.ts` parses the shared priority/comma-list option shapes; `errors.ts` turns an `ApiError` envelope into the inline one-liner. `vitest.config.ts` restricts `include` to `src/lib/**/*.test.ts`, so a page or component needs the `include` glob (and a jsdom/render-test setup) widened before its test would run.

### Repo root — build, theme, proxy, CI
**Purpose**: the Vite/Biome/TypeScript toolchain, the theme tokens and the dev-server wiring.
**Files**: `vite.config.ts`, `vitest.config.ts`, `biome.json`, `tsconfig.json`, `tsconfig.app.json`, `tsconfig.node.json`; `src/index.css`; `index.html`; `package.json`; `.env.example`; `.github/workflows/ci.yml`
**Seam(s)**: `vite.config.ts` owns the production `base` path and, via `loadEnv`, the dev server's port (`FRONTEND_DEV_PORT`, default `8143`, strict) and `/api` proxy (`VITE_API_TARGET`, default `http://localhost:8140`). The dev proxy injects `Authorization: Bearer ${AUTH__API_TOKEN}` from `frontend/.env`, mirroring the image's nginx proxy — the SPA never holds the token. `src/index.css`'s `@theme` block is the token source (no `tailwind.config.js`); `package.json`'s `check` script (typecheck + Biome + Vitest) is the fast gate, mirrored by CI.

## Entry points

- `index.html` — the Vite document; loads `src/main.tsx`.
- `src/main.tsx` — mounts React with the TanStack `QueryClient` and the browser router (`basename` from `BASE_URL`).
- `src/App.tsx` — the route table: `Layout` as the shell with `Console` as the index route.
- `vite.config.ts` — the dev server (port `FRONTEND_DEV_PORT`, default `8143`, strict) and the `/api` proxy, including the dev-only Bearer injection.
