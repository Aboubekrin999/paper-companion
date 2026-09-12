# Paper Companion — Web

Next.js 16 (App Router) frontend for [paper-companion](../README.md). Talks to the [`api/`](../api/README.md) FastAPI backend over HTTP/SSE for streaming RAG responses.

## Local development

```bash
cd web
npm install

# Copy env template and fill in values
cp .env.example .env.local

npm run dev
```

Open <http://localhost:3000>.

A Supabase URL and anon key are required for every route, not just sign-in: the auth middleware runs on each request, so with an empty `.env.local` the dev server returns 500 rather than rendering a signed-out page. The API base URL is configured in the same file — see `.env.example`.

Other scripts:

```bash
npm run build      # production build
npm run typecheck  # tsc --noEmit
```

## Stack

| Layer | Choice |
|---|---|
| Framework | Next.js 16 (App Router) + React 19 + TypeScript |
| Styling | Tailwind CSS v4 |
| Auth | Supabase SSR (`@supabase/ssr`) |
| Hosting | Vercel |

Reasoning in [`../docs/DECISIONS.md`](../docs/DECISIONS.md).

## Deployment

This directory deploys as a separate Vercel project from `api/`.

```bash
# From the web/ directory:
vercel link        # one-time
vercel             # preview deploy
vercel --prod      # production deploy
```

## Structure

```
src/
  app/           # App Router routes
  utils/         # Supabase client + helpers
  middleware.ts  # Auth session refresh
public/          # Static assets
```
