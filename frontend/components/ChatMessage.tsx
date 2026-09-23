import ReactMarkdown from "react-markdown";

import type { Citation } from "@/lib/api";
import Citations from "@/components/Citations";

export interface ChatMessageData {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  isError?: boolean;
}

// Assistant answers sometimes come back with markdown syntax (**bold**,
// bullet lists) from the underlying model -- render it properly instead of
// showing literal ** characters. User messages are plain text as typed, no
// need to markdown-render those.
const markdownComponents = {
  p: (props: React.ComponentProps<"p">) => <p className="my-1 first:mt-0 last:mb-0" {...props} />,
  strong: (props: React.ComponentProps<"strong">) => <strong className="font-semibold" {...props} />,
  ul: (props: React.ComponentProps<"ul">) => <ul className="my-1 list-inside list-disc space-y-0.5" {...props} />,
  ol: (props: React.ComponentProps<"ol">) => <ol className="my-1 list-inside list-decimal space-y-0.5" {...props} />,
  code: (props: React.ComponentProps<"code">) => (
    <code className="rounded bg-black/10 px-1 py-0.5 font-mono text-xs dark:bg-white/10" {...props} />
  ),
  a: (props: React.ComponentProps<"a">) => <a className="underline" target="_blank" rel="noreferrer" {...props} />,
};

export default function ChatMessage({ message }: { message: ChatMessageData }) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-3 ${
          isUser
            ? "bg-neutral-900 text-white dark:bg-neutral-100 dark:text-neutral-900"
            : message.isError
              ? "border border-red-200 bg-red-50 text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200"
              : "bg-neutral-100 text-neutral-900 dark:bg-neutral-800 dark:text-neutral-100"
        }`}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap text-sm">{message.content}</p>
        ) : (
          <div className="text-sm">
            <ReactMarkdown components={markdownComponents}>{message.content}</ReactMarkdown>
          </div>
        )}
        {!isUser && message.citations && <Citations citations={message.citations} />}
      </div>
    </div>
  );
}
