import { createClient } from "@/utils/supabase/server";
import { signOut } from "./actions";

export default async function Home() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100">
      <div className="mx-auto max-w-3xl px-6 py-12">
        <header className="mb-12 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">
              Paper Companion
            </h1>
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

        <section className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-8">
          <h2 className="text-lg font-medium">Your library</h2>
          <p className="mt-2 text-sm text-zinc-400">
            Empty for now. Upload a PDF or paste an arXiv link to get started.
          </p>
          <p className="mt-6 text-xs text-zinc-600">
            The ingest pipeline ships in week 2 — see{" "}
            <a
              href="https://github.com/Aboubekrin999/paper-companion/blob/main/docs/ROADMAP.md"
              className="underline transition hover:text-zinc-400"
            >
              ROADMAP.md
            </a>
            .
          </p>
        </section>
      </div>
    </main>
  );
}
