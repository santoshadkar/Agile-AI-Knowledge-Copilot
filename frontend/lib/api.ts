const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type DomainFilter = "agile-coaching" | "claude-certification" | "both";
export type IngestDomain = "agile-coaching" | "claude-certification";

export interface Citation {
  index: number;
  domain: string;
  source: string;
  heading_path: string;
}

export interface ChatResponse {
  answer: string;
  citations: Citation[];
  domains_searched: string[];
}

export interface IngestResponse {
  source: string;
  domain: string;
  chunk_count: number;
  confidentiality_flags: string[];
  // The backend responds as soon as the file is validated and chunked --
  // the actual embed+upsert runs afterward in the background (a large
  // document blocking the full request was timing out on Render's free
  // tier). chunk_count is accurate (chunking already happened), but the
  // document isn't searchable in chat until a bit after this response.
  status: "processing";
}

/** Thrown for the 422 the backend returns when a file trips the
 * confidentiality guard -- carries the specific reasons so the UI can show
 * them and offer a "ingest anyway" retry with force=true, rather than just
 * a generic error message. */
export class ConfidentialityFlagError extends Error {
  reasons: string[];
  source: string;

  constructor(message: string, reasons: string[], source: string) {
    super(message);
    this.name = "ConfidentialityFlagError";
    this.reasons = reasons;
    this.source = source;
  }
}

async function extractErrorMessage(res: Response): Promise<string> {
  const body = await res.json().catch(() => null);
  if (typeof body?.detail === "string") return body.detail;
  return `Request failed (${res.status})`;
}

export async function sendChatMessage(
  message: string,
  domainFilter: DomainFilter,
): Promise<ChatResponse> {
  const res = await fetch(`${API_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, domain_filter: domainFilter }),
  });

  if (!res.ok) {
    throw new Error(await extractErrorMessage(res));
  }
  return res.json();
}

export async function ingestDocument(
  file: File,
  domain: IngestDomain,
  force = false,
): Promise<IngestResponse> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("domain", domain);
  formData.append("force", String(force));

  const res = await fetch(`${API_URL}/ingest`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    if (res.status === 422) {
      const body = await res.json().catch(() => null);
      const detail = body?.detail;
      if (detail && typeof detail === "object" && Array.isArray(detail.reasons)) {
        throw new ConfidentialityFlagError(detail.message, detail.reasons, detail.source);
      }
    }
    throw new Error(await extractErrorMessage(res));
  }
  return res.json();
}
