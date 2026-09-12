"use server";

import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";
import { createClient } from "@/utils/supabase/server";
import { ApiError, ingestPaper } from "@/lib/api";

export async function signOut() {
  const supabase = await createClient();
  await supabase.auth.signOut();
  redirect("/login");
}

/** The caller's Supabase access token, or null when signed out. */
export async function accessToken(): Promise<string | null> {
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  return session?.access_token ?? null;
}

export interface IngestState {
  error?: string;
}

/**
 * Ingest an arXiv reference submitted from the library form.
 *
 * Returns the error rather than throwing so the form can render it in
 * place; a thrown error here would replace the whole library with an
 * error boundary for what is usually a typo in an arXiv id.
 */
export async function ingestAction(
  _previous: IngestState,
  formData: FormData,
): Promise<IngestState> {
  const reference = String(formData.get("reference") ?? "").trim();
  if (!reference) {
    return { error: "Enter an arXiv link or id." };
  }

  const token = await accessToken();
  if (!token) redirect("/login");

  try {
    await ingestPaper(token, reference);
  } catch (error) {
    if (error instanceof ApiError) {
      return { error: describe(error) };
    }
    return { error: "Could not reach the API. Is it running?" };
  }

  revalidatePath("/");
  return {};
}

function describe(error: ApiError): string {
  if (error.status === 400) return `That doesn't look like an arXiv reference: ${error.message}`;
  if (error.status === 502) return "arXiv could not be reached. Try again shortly.";
  if (error.status === 503) return "The API is not configured for sign-in yet.";
  return error.message;
}
