import React, { useEffect, useRef } from "react";

export interface Message {
  id: string;
  role: "user" | "assistant";
  /** Complete text for user messages; partial accumulation for assistant during streaming */
  content: string;
  /** True while the assistant is still streaming this message */
  streaming?: boolean;
}

interface Props {
  messages: Message[];
  greeting: string;
}

/** Typing indicator shown while assistant is streaming a new message */
function TypingIndicator() {
  return (
    <div className="message-row assistant">
      <div className="typing-indicator">
        <span className="typing-dot" />
        <span className="typing-dot" />
        <span className="typing-dot" />
      </div>
    </div>
  );
}

export function MessageList({ messages, greeting }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom whenever messages change
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Are we currently streaming (last message is assistant + streaming)?
  const lastMsg = messages[messages.length - 1];
  const isStreaming =
    lastMsg?.role === "assistant" && lastMsg.streaming === true;

  return (
    <div className="messages">
      {/* Greeting */}
      <p className="message-greeting">{greeting}</p>

      {messages.map((msg) => (
        <div key={msg.id} className={`message-row ${msg.role}`}>
          <div className="message-bubble">
            {msg.content}
            {/* Blinking cursor while streaming */}
            {msg.streaming && <span style={{ opacity: 0.6 }}>▌</span>}
          </div>
        </div>
      ))}

      {/* Show typing dots only if assistant hasn't started content yet */}
      {isStreaming && lastMsg.content === "" && <TypingIndicator />}

      <div ref={bottomRef} />
    </div>
  );
}
