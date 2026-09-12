import Link from "next/link";
import { createClient } from "@/utils/supabase/server";
import { accessToken, signOut } from "./actions";
import { listPapers, type Paper } from "@/lib/api";
import { IngestForm } from "@/components/ingest-form";

export default async function Home() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  const token = await accessToken();
  let papers: Paper[] = [];
  let apiError: string | null = null;

  if (token) {
    try {
      papers = await listPapers(token);
    } catch {
      apiError = "Could not reach the API. Start it with `uvicorn api.index:app --reload --port 8000`.";
    }
  }

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100">
      <div className="mx-auto max-w-3xl px-6 py-12">
        <header className="mb-10 flex items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Paper Companion</h1>
            <p className="mt-1 text-sm text-zinc-500">{user?.email}</p>
          </div>
          <form action={signOut}>
            <button
              type="submit"
              className="text-sm text-zinc-400 transition hover:text-zinc-100"
            >
              Sign out
            </button>
          </form>
        </header>

        <IngestForm />

        <section className="mt-10">
          <h2 className="text-lg font-medium">Your library</h2>

          {apiError ? (
            <p className="mt-3 rounded-lg border border-amber-900/60 bg-amber-950/30 p-4 text-sm text-amber-200">
              {apiError}
            </p>
          ) : papers.length === 0 ? (
            <p className="mt-3 text-sm text-zinc-400">
              Empty for now. Paste an arXiv link above to add your first paper.
            </p>
          ) : (
            <ul className="mt-4 space-y-2">
              {papers.map((paper) => (
                <li key={paper.id}>
                  <Link
                    href={`/papers/${encodeURIComponent(paper.id)}`}
                    className="block rounded-xl border border-zinc-800 bg-zinc-900/40 p-4 transition hover:border-zinc-700 hover:bg-zinc-900"
                  >
                    <span className="font-medium">arXiv:{paper.arxiv_id}</span>
                    <span className="mt-1 block text-xs text-zinc-500">
                      {paper.page_count} pages · {paper.chunk_count} chunks
                      {paper.version ? ` · v${paper.version}` : ""}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </main>
  );
}
