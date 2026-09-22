import type { Citation } from "@/lib/api";
import Citations from "@/components/Citations";

export interface ChatMessageData {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  isError?: boolean;
}

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
        <p className="whitespace-pre-wrap text-sm">{message.content}</p>
        {!isUser && message.citations && <Citations citations={message.citations} />}
      </div>
    </div>
  );
}
