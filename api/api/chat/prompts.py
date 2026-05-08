"""
Prompt templates for the chat orchestrator.

The system prompt is the contract between the retrieval layer and the
model: answer only from context, cite via the chunk IDs we hand over,
say "not in the paper" rather than guess. Drift here changes
faithfulness scores, so the prompt is centralised and version-tagged
in commit history.
"""

SYSTEM_PROMPT = """You are a research assistant answering questions about a single academic paper.

Answer ONLY using information that appears in the provided <context> blocks. Each block is tagged with a chunk_id and page number. When you make a claim, cite the chunk_id(s) that support it in square brackets, like [c-2401.12345-12].

If the context does not contain enough information to answer the question, say so plainly. Do not guess. Do not draw on outside knowledge of the topic.

Quote sparingly. Prefer to paraphrase the source in your own words and cite, rather than copying long passages."""


def build_user_message(question: str, context_blocks: list[str]) -> str:
    """Format the retrieved chunks and the user's question into a single message body."""
    if not context_blocks:
        joined = "(no relevant context retrieved)"
    else:
        joined = "\n\n".join(context_blocks)
    return f"<context>\n{joined}\n</context>\n\nQuestion: {question}"


def format_chunk_block(chunk_id: str, page_number: int | None, content: str) -> str:
    """One context block in the format the system prompt promises."""
    page_label = f"page {page_number}" if page_number is not None else "page n/a"
    return f"[{chunk_id} | {page_label}]\n{content}"
