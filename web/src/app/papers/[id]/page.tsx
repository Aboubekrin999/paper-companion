import Link from "next/link";
import { notFound } from "next/navigation";
import { accessToken } from "@/app/actions";
import { ApiError, getPaper } from "@/lib/api";
import { ChatPanel } from "@/components/chat-panel";

export default async function PaperPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const token = await accessToken();
  if (!token) notFound();

  let paper;
  try {
    paper = await getPaper(token, id);
  } catch (error) {
    // The API reports another user's paper as 404 by design, so this is
    // "not yours or not there" — the page makes no distinction either.
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error;
  }

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100">
      <div className="mx-auto max-w-3xl px-6 py-12">
        <Link
          href="/"
          className="text-sm text-zinc-500 transition hover:text-zinc-300"
        >
          ← Library
        </Link>

        <header className="mt-6 mb-8">
          <h1 className="text-2xl font-semibold tracking-tight">
            arXiv:{paper.arxiv_id}
          </h1>
          <p className="mt-1 text-sm text-zinc-500">
            {paper.page_count} pages · {paper.chunk_count} chunks ·{" "}
            <a
              href={paper.abs_url}
              target="_blank"
              rel="noreferrer"
              className="underline transition hover:text-zinc-300"
            >
              arXiv page
            </a>
          </p>
        </header>

        <ChatPanel paperId={paper.id} token={token} />
      </div>
    </main>
  );
}
