/**
 * RateLimitScreen — shown when the backend fires a `rate_limit` SSE event.
 *
 * Two CTAs:
 *   1. Book a meeting via Cal.com
 *   2. Leave email for the owner to reach out (lead capture)
 */
import React, { useState } from "react";
import type { GatePayload } from "../hooks/useSSE";

interface Props {
  payload: GatePayload;
  /** Called when visitor submits their email for lead capture */
  onEmailSubmit: (email: string) => Promise<void>;
}

export function RateLimitScreen({ payload, onEmailSubmit }: Props) {
  const calUrl = payload.cal_url ?? "";
  const message =
    payload.message ??
    "You've reached today's question limit. Come back tomorrow to continue chatting!";

  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [errorMsg, setErrorMsg] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = email.trim();
    if (!trimmed || !trimmed.includes("@")) {
      setErrorMsg("Please enter a valid email address.");
      return;
    }
    setErrorMsg("");
    setStatus("loading");
    try {
      await onEmailSubmit(trimmed);
      setStatus("success");
    } catch {
      setStatus("error");
      setErrorMsg("Something went wrong. Please try again.");
    }
  }

  return (
    <div className="ratelimit-screen">
      <span className="ratelimit-icon">☕</span>
      <h2 className="ratelimit-title">That's a wrap for today!</h2>
      <p className="ratelimit-message">{message}</p>

      <div className="ratelimit-actions">
        {/* Cal.com booking */}
        {calUrl && (
          <a
            className="ratelimit-cal-btn"
            href={calUrl}
            target="_blank"
            rel="noopener noreferrer"
          >
            📅 Book a meeting
          </a>
        )}

        {/* Email lead capture */}
        {status === "success" ? (
          <p className="ratelimit-success">
            ✅ Got it! We'll be in touch soon.
          </p>
        ) : (
          <form className="ratelimit-email-form" onSubmit={handleSubmit}>
            <p className="ratelimit-email-label">
              Leave your email and we'll reach out:
            </p>
            <div className="ratelimit-email-row">
              <input
                className="ratelimit-email-input"
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={status === "loading"}
                autoComplete="email"
              />
              <button
                className="ratelimit-email-submit"
                type="submit"
                disabled={status === "loading"}
              >
                {status === "loading" ? "..." : "→"}
              </button>
            </div>
            {errorMsg && <p className="gate-error">{errorMsg}</p>}
          </form>
        )}
      </div>
    </div>
  );
}
