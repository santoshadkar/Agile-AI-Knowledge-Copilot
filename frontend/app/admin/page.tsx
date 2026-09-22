"use client";

import { useState } from "react";
import Link from "next/link";

import { ingestDocument, ConfidentialityFlagError, type IngestDomain, type IngestResponse } from "@/lib/api";

type Status =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "success"; result: IngestResponse }
  | { kind: "error"; message: string }
  | { kind: "confidentiality-flag"; reasons: string[]; source: string };

export default function AdminPage() {
  const [file, setFile] = useState<File | null>(null);
  const [domain, setDomain] = useState<IngestDomain>("agile-coaching");
  const [status, setStatus] = useState<Status>({ kind: "idle" });

  async function runIngest(force: boolean) {
    if (!file) return;
    setStatus({ kind: "loading" });
    try {
      const result = await ingestDocument(file, domain, force);
      setStatus({ kind: "success", result });
      setFile(null);
    } catch (err) {
      if (err instanceof ConfidentialityFlagError) {
        setStatus({ kind: "confidentiality-flag", reasons: err.reasons, source: err.source });
      } else {
        setStatus({ kind: "error", message: err instanceof Error ? err.message : "Upload failed." });
      }
    }
  }

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-2xl flex-col gap-6 p-4">
      <header className="flex items-center justify-between gap-4 border-b border-neutral-200 pb-4 dark:border-neutral-800">
        <div>
          <h1 className="text-lg font-semibold">Admin — Upload Documents</h1>
          <p className="text-xs text-neutral-500">Add a source document to the knowledge base</p>
        </div>
        <Link href="/" className="text-sm text-neutral-500 underline hover:text-neutral-800 dark:hover:text-neutral-200">
          Chat
        </Link>
      </header>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          runIngest(false);
        }}
        className="flex flex-col gap-4"
      >
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium">File (PDF, DOCX, or Markdown)</label>
          <input
            type="file"
            accept=".pdf,.docx,.md"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="text-sm"
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium">Domain</label>
          <select
            value={domain}
            onChange={(e) => setDomain(e.target.value as IngestDomain)}
            className="rounded-lg border border-neutral-300 bg-transparent px-3 py-2 text-sm dark:border-neutral-700"
          >
            <option value="agile-coaching">Agile Coaching</option>
            <option value="claude-certification">Claude Certification</option>
          </select>
        </div>

        <button
          type="submit"
          disabled={!file || status.kind === "loading"}
          className="self-start rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-40 dark:bg-neutral-100 dark:text-neutral-900"
        >
          {status.kind === "loading" ? "Uploading…" : "Upload"}
        </button>
      </form>

      {status.kind === "success" && (
        <div className="rounded-lg border border-green-200 bg-green-50 p-4 text-sm text-green-800 dark:border-green-900 dark:bg-green-950 dark:text-green-200">
          Ingested <strong>{status.result.source}</strong> into <strong>{status.result.domain}</strong> —{" "}
          {status.result.chunk_count} chunks.
        </div>
      )}

      {status.kind === "error" && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200">
          {status.message}
        </div>
      )}

      {status.kind === "confidentiality-flag" && (
        <div className="flex flex-col gap-3 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200">
          <p>
            <strong>{status.source}</strong> looks like it might be proprietary or confidential:
          </p>
          <ul className="list-inside list-disc">
            {status.reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
          <p>Only upload it if you&apos;re sure it doesn&apos;t contain anything sensitive.</p>
          <button
            type="button"
            onClick={() => runIngest(true)}
            className="self-start rounded-lg border border-amber-400 px-3 py-1.5 text-sm font-medium hover:bg-amber-100 dark:hover:bg-amber-900"
          >
            Ingest anyway
          </button>
        </div>
      )}
    </main>
  );
}
