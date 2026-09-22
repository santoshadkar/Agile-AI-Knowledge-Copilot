"use client";

import type { DomainFilter } from "@/lib/api";

const OPTIONS: { value: DomainFilter; label: string }[] = [
  { value: "both", label: "Both" },
  { value: "agile-coaching", label: "Agile Coaching" },
  { value: "claude-certification", label: "Claude Certification" },
];

export default function DomainFilterSelect({
  value,
  onChange,
}: {
  value: DomainFilter;
  onChange: (value: DomainFilter) => void;
}) {
  return (
    <div className="inline-flex rounded-lg border border-neutral-300 p-1 dark:border-neutral-700">
      {OPTIONS.map((option) => (
        <button
          key={option.value}
          type="button"
          onClick={() => onChange(option.value)}
          className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
            value === option.value
              ? "bg-neutral-900 text-white dark:bg-neutral-100 dark:text-neutral-900"
              : "text-neutral-600 hover:bg-neutral-100 dark:text-neutral-400 dark:hover:bg-neutral-800"
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
