"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";

import { sendChatMessage, type DomainFilter } from "@/lib/api";
import ChatMessage, { type ChatMessageData } from "@/components/ChatMessage";
import DomainFilterSelect from "@/components/DomainFilterSelect";

export default function Home() {
  const [messages, setMessages] = useState<ChatMessageData[]>([]);
  const [domainFilter, setDomainFilter] = useState<DomainFilter>("both");
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function handleSend() {
    const trimmed = input.trim();
    if (!trimmed || loading) return;

    setMessages((prev) => [...prev, { role: "user", content: trimmed }]);
    setInput("");
    setLoading(true);

    try {
      const response = await sendChatMessage(trimmed, domainFilter);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: response.answer, citations: response.citations },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: err instanceof Error ? err.message : "Something went wrong.",
          isError: true,
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <main className="mx-auto flex h-screen w-full max-w-3xl flex-col p-4">
      <header className="flex items-center justify-between gap-4 border-b border-neutral-200 pb-4 dark:border-neutral-800">
        <div>
          <h1 className="text-lg font-semibold">Agile & AI Knowledge Copilot</h1>
          <p className="text-xs text-neutral-500">Ask about agile coaching or Claude certification material</p>
        </div>
        <Link href="/admin" className="text-sm text-neutral-500 underline hover:text-neutral-800 dark:hover:text-neutral-200">
          Admin
        </Link>
      </header>

      <div className="flex items-center gap-2 py-3">
        <span className="text-xs font-medium text-neutral-500">Search:</span>
        <DomainFilterSelect value={domainFilter} onChange={setDomainFilter} />
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto py-2">
        {messages.length === 0 && (
          <p className="mt-8 text-center text-sm text-neutral-400">
            Ask a question to get started. Citations show which document and domain each answer drew from.
          </p>
        )}
        {messages.map((message, i) => (
          <ChatMessage key={i} message={message} />
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="rounded-2xl bg-neutral-100 px-4 py-3 text-sm text-neutral-400 dark:bg-neutral-800">
              Thinking…
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="flex items-end gap-2 border-t border-neutral-200 pt-4 dark:border-neutral-800">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask a question…"
          rows={1}
          className="flex-1 resize-none rounded-lg border border-neutral-300 bg-transparent px-3 py-2 text-sm outline-none focus:border-neutral-500 dark:border-neutral-700"
        />
        <button
          type="button"
          onClick={handleSend}
          disabled={loading || !input.trim()}
          className="rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-40 dark:bg-neutral-100 dark:text-neutral-900"
        >
          Send
        </button>
      </div>
    </main>
  );
}
