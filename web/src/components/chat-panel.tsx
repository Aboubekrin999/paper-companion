"use client";

import { useRef, useState } from "react";
import { streamChat, type Citation } from "@/lib/api";

interface Exchange {
  question: string;
  answer: string;
  citations: Citation[];
  error?: string;
}

export function ChatPanel({
  paperId,
  token,
}: {
  paperId: string;
  token: string;
}) {
  const [question, setQuestion] = useState("");
  const [exchanges, setExchanges] = useState<Exchange[]>([]);
  const [streaming, setStreaming] = useState(false);
  const abort = useRef<AbortController | null>(null);

  async function ask(event: React.FormEvent) {
    event.preventDefault();
    const asked = question.trim();
    if (!asked || streaming) return;

    setQuestion("");
    setStreaming(true);
    // Append the exchange up front so the question is visible while the
    // answer streams in underneath it.
    const index = exchanges.length;
    setExchanges((prev) => [...prev, { question: asked, answer: "", citations: [] }]);

    const controller = new AbortController();
    abort.current = controller;

    try {
      for await (const event of streamChat(token, paperId, asked, 5, controller.signal)) {
        if (event.type === "citations") {
          update(index, (ex) => ({ ...ex, citations: event.citations }));
        } else if (event.type === "token") {
          update(index, (ex) => ({ ...ex, answer: ex.answer + event.text }));
        }
      }
    } catch (error) {
      if (!controller.signal.aborted) {
        update(index, (ex) => ({
          ...ex,
          error: error instanceof Error ? error.message : "Something went wrong.",
        }));
      }
    } finally {
      setStreaming(false);
      abort.current = null;
    }
  }

  function update(index: number, apply: (ex: Exchange) => Exchange) {
    setExchanges((prev) =>
      prev.map((ex, i) => (i === index ? apply(ex) : ex)),
    );
  }

  function stop() {
    abort.current?.abort();
  }

  return (
    <div className="space-y-6">
      {exchanges.map((exchange, i) => (
        <article key={i} className="space-y-3">
          <p className="font-medium">{exchange.question}</p>

          {exchange.citations.length > 0 && (
            <ul className="flex flex-wrap gap-1.5">
              {exchange.citations.map((citation) => (
                <li
                  key={citation.chunk_id}
                  title={citation.snippet}
                  className="rounded-full border border-zinc-800 bg-zinc-900 px-2.5 py-0.5 text-xs text-zinc-400"
                >
                  {citation.page_number != null
                    ? `p.${citation.page_number}`
                    : citation.chunk_id}
                  <span className="ml-1.5 text-zinc-600">
                    {citation.score.toFixed(2)}
                  </span>
                </li>
              ))}
            </ul>
          )}

          {exchange.error ? (
            <p role="alert" className="text-sm text-red-400">
              {exchange.error}
            </p>
          ) : (
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-zinc-300">
              {exchange.answer}
              {streaming && i === exchanges.length - 1 && (
                <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-zinc-500 align-middle" />
              )}
            </p>
          )}
        </article>
      ))}

      <form onSubmit={ask} className="flex gap-2">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask a question about this paper…"
          aria-label="Question"
          className="flex-1 rounded-lg border border-zinc-800 bg-zinc-900/60 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-zinc-600 focus:outline-none"
        />
        {streaming ? (
          <button
            type="button"
            onClick={stop}
            className="rounded-lg border border-zinc-700 px-4 py-2 text-sm text-zinc-300 transition hover:bg-zinc-900"
          >
            Stop
          </button>
        ) : (
          <button
            type="submit"
            disabled={!question.trim()}
            className="rounded-lg bg-zinc-100 px-4 py-2 text-sm font-medium text-zinc-900 transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-50"
          >
            Ask
          </button>
        )}
      </form>
    </div>
  );
}
