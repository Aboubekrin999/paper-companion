"use client";

import { useActionState } from "react";
import { useFormStatus } from "react-dom";
import { ingestAction, type IngestState } from "@/app/actions";

const INITIAL: IngestState = {};

export function IngestForm() {
  const [state, action] = useActionState(ingestAction, INITIAL);

  return (
    <form action={action} className="space-y-2">
      <label htmlFor="reference" className="block text-sm text-zinc-400">
        Add a paper
      </label>
      <div className="flex gap-2">
        <input
          id="reference"
          name="reference"
          type="text"
          placeholder="arxiv.org/abs/2401.12345 or 2401.12345"
          autoComplete="off"
          className="flex-1 rounded-lg border border-zinc-800 bg-zinc-900/60 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-zinc-600 focus:outline-none"
        />
        <SubmitButton />
      </div>
      {state.error ? (
        <p role="alert" className="text-sm text-red-400">
          {state.error}
        </p>
      ) : null}
    </form>
  );
}

function SubmitButton() {
  // Ingest fetches and parses a PDF, so it is slow enough that an
  // un-disabled button would collect double submissions.
  const { pending } = useFormStatus();
  return (
    <button
      type="submit"
      disabled={pending}
      className="rounded-lg bg-zinc-100 px-4 py-2 text-sm font-medium text-zinc-900 transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-50"
    >
      {pending ? "Adding…" : "Add"}
    </button>
  );
}
