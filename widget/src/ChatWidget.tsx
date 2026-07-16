/**
 * ChatWidget — the main chat UI.
 *
 * Receives config from the web component (index.tsx) via props.
 * Handles four UI screens:
 *   1. "chat"         — normal conversation view
 *   2. "identity_gate"— collect name/email/company before continuing
 *   3. "rate_limit"   — daily limit hit, show Cal.com + email CTAs
 *
 * SSE flow:
 *   send() → EventSource opens → tokens arrive → messages[last].content grows
 *   → [DONE] received → streaming flag cleared
 *   → rate_limit / identity_gate event → switch screen
 */
import React, { useState, useRef, useCallback, useEffect } from "react";
import { MessageList, type Message } from "./components/MessageList";
import { SuggestedQuestions } from "./components/SuggestedQuestions";
import { IdentityGateScreen } from "./components/IdentityGateScreen";
import { RateLimitScreen } from "./components/RateLimitScreen";
import { useSSE, type AnswerMetadata, type GatePayload } from "./hooks/useSSE";
import {
  getSessionId,
  getSavedEmail,
  getSavedName,
} from "./hooks/useSession";

export interface WidgetConfig {
  apiKey: string;
  baseUrl: string;
  greeting: string;
  suggestedQuestions: string[];
  themeColor: string;
  ownerName: string;
}

type Screen = "chat" | "identity_gate" | "rate_limit";

let msgCounter = 0;
function nextId() {
  return `m${++msgCounter}`;
}

export function ChatWidget({ config }: { config: WidgetConfig }) {
  const sessionId = useRef(getSessionId()).current;

  // --- UI state ---
  const [isOpen, setIsOpen] = useState(false);
  const [screen, setScreen] = useState<Screen>("chat");
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [gatePayload, setGatePayload] = useState<GatePayload | null>(null);
  // Visitor metadata collected at identity gate
  const [visitorEmail, setVisitorEmail] = useState(getSavedEmail());
  const [visitorName, setVisitorName] = useState(getSavedName());
  // Question that triggered the gate — re-sent after gate submission
  const pendingQuestionRef = useRef<string>("");

  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Whether suggested questions are still visible (hide after first user message)
  const showSuggestions = messages.length === 0;

  // --- SSE hook ---
  const { state: sseState, send: sseSend } = useSSE({
    apiKey: config.apiKey,
    baseUrl: config.baseUrl,
    sessionId,
    onToken: (token) => {
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (!last || last.role !== "assistant") return prev;
        return [
          ...prev.slice(0, -1),
          { ...last, content: last.content + token },
        ];
      });
    },
    onDone: () => {
      // Mark the last assistant message as no longer streaming
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (!last || last.role !== "assistant") return prev;
        return [...prev.slice(0, -1), { ...last, streaming: false }];
      });
    },
    onGate: (payload) => {
      setGatePayload(payload);
      if (payload.reason === "rate_limit") {
        setScreen("rate_limit");
      } else {
        setScreen("identity_gate");
      }
    },
    onMetadata: (metadata: AnswerMetadata) => {
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (!last || last.role !== "assistant") return prev;
        return [
          ...prev.slice(0, -1),
          {
            ...last,
            status: metadata.status,
            evidence: metadata.evidence,
            snapshotVersion: metadata.snapshot_version,
          },
        ];
      });
    },
    onError: (msg) => {
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last?.role === "assistant" && last.streaming) {
          return [
            ...prev.slice(0, -1),
            { ...last, content: msg, streaming: false },
          ];
        }
        return [
          ...prev,
          { id: nextId(), role: "assistant", content: msg, streaming: false },
        ];
      });
    },
  });

  const isStreaming = sseState === "streaming";

  /** Core send function — adds user bubble, creates empty assistant bubble, starts SSE */
  const sendQuestion = useCallback(
    (question: string, email?: string, name?: string) => {
      const q = question.trim();
      if (!q || isStreaming) return;

      // Add user message
      setMessages((prev) => [
        ...prev,
        { id: nextId(), role: "user", content: q },
        { id: nextId(), role: "assistant", content: "", streaming: true },
      ]);

      sseSend(q, (email ?? visitorEmail) || undefined, (name ?? visitorName) || undefined);
    },
    [isStreaming, sseSend, visitorEmail, visitorName]
  );

  /** Handle form submit from input area */
  function handleSend() {
    const q = input.trim();
    if (!q || isStreaming) return;
    setInput("");
    sendQuestion(q);
  }

  /** Auto-resize textarea as user types */
  function handleInputChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    setInput(e.target.value);
    const el = e.target;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
  }

  /** Send on Enter (Shift+Enter = newline) */
  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  /** Identity gate submitted — save details and re-send the pending question */
  function handleGateSubmit(name: string, email: string, _company: string) {
    setVisitorName(name);
    setVisitorEmail(email);
    setScreen("chat");
    const pending = pendingQuestionRef.current;
    pendingQuestionRef.current = "";
    if (pending) {
      // Small delay so screen switch renders first
      setTimeout(() => sendQuestion(pending, email, name), 50);
    }
  }

  // When user sends a question and we receive identity_gate, store the question
  // so we can re-send it after gate is cleared.
  useEffect(() => {
    if (screen === "identity_gate") {
      // The last user message is the one that triggered the gate
      const lastUser = [...messages].reverse().find((m) => m.role === "user");
      if (lastUser) {
        pendingQuestionRef.current = lastUser.content;
        // Remove the empty streaming assistant bubble (gate replaced it)
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last?.role === "assistant" && last.streaming) {
            return prev.slice(0, -1);
          }
          return prev;
        });
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [screen]);

  // Focus textarea when panel opens
  useEffect(() => {
    if (isOpen && screen === "chat") {
      textareaRef.current?.focus();
    }
  }, [isOpen, screen]);

  return (
    <>
      {/* ----- Floating bubble ----- */}
      <button
        className="bubble"
        onClick={() => setIsOpen((o) => !o)}
        aria-label={isOpen ? "Close chat" : "Open chat"}
        type="button"
      >
        {isOpen ? "✕" : "💬"}
      </button>

      {/* ----- Chat panel ----- */}
      {isOpen && (
        <div className="panel" role="dialog" aria-label="Career assistant">
          {/* Header */}
          <div className="header">
            <div className="header-avatar">🤖</div>
            <div className="header-info">
              <div className="header-name">{config.ownerName}'s Assistant</div>
              <div className="header-status">
                {isStreaming ? "Typing…" : "Online"}
              </div>
            </div>
            <button
              className="header-close"
              onClick={() => setIsOpen(false)}
              aria-label="Close"
              type="button"
            >
              ✕
            </button>
          </div>

          {/* Screen routing */}
          {screen === "rate_limit" && gatePayload ? (
            <RateLimitScreen
              payload={gatePayload}
              onEmailSubmit={async (email) => {
                const res = await fetch(`${config.baseUrl}/api/v1/visitor/lead`, {
                  method: "POST",
                  headers: {
                    "Content-Type": "application/json",
                    "X-API-Key": config.apiKey,
                  },
                  body: JSON.stringify({ email, session_id: sessionId }),
                });
                if (!res.ok) throw new Error("Failed to submit");
              }}
            />
          ) : screen === "identity_gate" ? (
            <IdentityGateScreen
              questionsAnswered={messages.filter((m) => m.role === "user").length}
              onSubmit={handleGateSubmit}
              defaultEmail={visitorEmail}
              defaultName={visitorName}
            />
          ) : (
            <>
              {/* Messages */}
              <MessageList messages={messages} greeting={config.greeting} />

              {/* Suggested questions (hidden after first message) */}
              {showSuggestions && (
                <SuggestedQuestions
                  questions={config.suggestedQuestions}
                  onSelect={(q) => sendQuestion(q)}
                />
              )}

              {/* Input */}
              <div className="input-area">
                <textarea
                  ref={textareaRef}
                  className="input-textarea"
                  rows={1}
                  placeholder="Ask about experience, skills, projects…"
                  value={input}
                  onChange={handleInputChange}
                  onKeyDown={handleKeyDown}
                  disabled={isStreaming}
                />
                <button
                  className="send-btn"
                  onClick={handleSend}
                  disabled={isStreaming || !input.trim()}
                  aria-label="Send"
                  type="button"
                >
                  ➤
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </>
  );
}
