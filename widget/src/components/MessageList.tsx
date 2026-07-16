import React, { useEffect, useRef } from "react";
import type { AnswerEvidence } from "../hooks/useSSE";

export interface Message {
  id: string;
  role: "user" | "assistant";
  /** Complete text for user messages; partial accumulation for assistant during streaming */
  content: string;
  /** True while the assistant is still streaming this message */
  streaming?: boolean;
  status?: "SUPPORTED" | "PARTIAL" | "UNANSWERABLE";
  evidence?: AnswerEvidence[];
  snapshotVersion?: number;
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
            {msg.role === "assistant" && !msg.streaming && msg.status && (
              <div className="answer-grounding">
                <span className={`answer-status ${msg.status.toLowerCase()}`}>
                  {msg.status === "SUPPORTED"
                    ? "Grounded"
                    : msg.status === "PARTIAL"
                      ? "Partially grounded"
                      : "No profile evidence"}
                </span>
                {msg.evidence && msg.evidence.length > 0 && (
                  <details className="answer-evidence">
                    <summary>
                      {msg.evidence.length} {msg.evidence.length === 1 ? "source" : "sources"}
                    </summary>
                    <div className="evidence-list">
                      {msg.evidence.map((evidence) => (
                        <div className="evidence-item" key={`${evidence.source_type}:${evidence.source_id}`}>
                          <span className="evidence-type">
                            {evidence.source_type.replace("_", " ")}
                          </span>
                          <strong>{evidence.title}</strong>
                          <p>{evidence.quote}</p>
                        </div>
                      ))}
                    </div>
                  </details>
                )}
              </div>
            )}
          </div>
        </div>
      ))}

      {/* Show typing dots only if assistant hasn't started content yet */}
      {isStreaming && lastMsg.content === "" && <TypingIndicator />}

      <div ref={bottomRef} />
    </div>
  );
}
