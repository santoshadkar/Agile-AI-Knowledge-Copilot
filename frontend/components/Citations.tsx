import type { Citation } from "@/lib/api";

const DOMAIN_LABELS: Record<string, string> = {
  "agile-coaching": "Agile Coaching",
  "claude-certification": "Claude Certification",
};

export default function Citations({ citations }: { citations: Citation[] }) {
  if (citations.length === 0) return null;

  return (
    <div className="mt-2 border-t border-neutral-200 pt-2 dark:border-neutral-800">
      <p className="mb-1 text-xs font-medium text-neutral-500">Sources consulted</p>
      <ul className="space-y-1">
        {citations.map((c) => (
          <li key={c.index} className="text-xs text-neutral-500">
            <span className="font-mono text-neutral-400">[{c.index}]</span>{" "}
            <span className="rounded bg-neutral-100 px-1.5 py-0.5 text-neutral-600 dark:bg-neutral-800 dark:text-neutral-400">
              {DOMAIN_LABELS[c.domain] ?? c.domain}
            </span>{" "}
            {c.source}
            {c.heading_path ? <span className="text-neutral-400"> :: {c.heading_path}</span> : null}
          </li>
        ))}
      </ul>
    </div>
  );
}
