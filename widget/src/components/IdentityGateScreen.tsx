/**
 * IdentityGateScreen — shown when the backend fires an `identity_gate` SSE event.
 *
 * Collects name (required) + email (required) + company (optional).
 * Saves email and name in localStorage so the form is pre-filled next visit.
 *
 * After submission, the parent ChatWidget calls send() again with the visitor
 * metadata attached, so the conversation continues seamlessly.
 */
import React, { useState } from "react";
import { saveVisitorEmail, saveVisitorName } from "../hooks/useSession";

interface Props {
  /** Number of questions the visitor has already asked */
  questionsAnswered: number;
  /** Called when visitor submits their details */
  onSubmit: (name: string, email: string, company: string) => void;
  /** Pre-filled values from localStorage */
  defaultEmail?: string;
  defaultName?: string;
}

export function IdentityGateScreen({
  questionsAnswered,
  onSubmit,
  defaultEmail = "",
  defaultName = "",
}: Props) {
  const [name, setName] = useState(defaultName);
  const [email, setEmail] = useState(defaultEmail);
  const [company, setCompany] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  function validate(): boolean {
    if (!name.trim()) {
      setError("Please enter your name.");
      return false;
    }
    if (!email.trim() || !email.includes("@")) {
      setError("Please enter a valid email address.");
      return false;
    }
    return true;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (!validate()) return;

    setSubmitting(true);
    saveVisitorEmail(email.trim());
    saveVisitorName(name.trim());
    onSubmit(name.trim(), email.trim(), company.trim());
  }

  const subtitle =
    questionsAnswered > 0
      ? `You've asked ${questionsAnswered} question${questionsAnswered === 1 ? "" : "s"}. Share your details to keep the conversation going.`
      : "Share your details to start chatting.";

  return (
    <div className="gate-screen">
      <span className="gate-icon">👋</span>
      <h2 className="gate-title">Just one quick step</h2>
      <p className="gate-subtitle">{subtitle}</p>

      <form className="gate-form" onSubmit={handleSubmit} noValidate>
        <input
          className="gate-input"
          type="text"
          placeholder="Your name *"
          value={name}
          onChange={(e) => setName(e.target.value)}
          autoComplete="name"
          required
        />
        <input
          className="gate-input"
          type="email"
          placeholder="Work email *"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="email"
          required
        />
        <input
          className="gate-input"
          type="text"
          placeholder="Company (optional)"
          value={company}
          onChange={(e) => setCompany(e.target.value)}
          autoComplete="organization"
        />

        {error && <p className="gate-error">{error}</p>}

        <button
          className="gate-submit-btn"
          type="submit"
          disabled={submitting}
        >
          {submitting ? "Continuing…" : "Continue chatting →"}
        </button>
      </form>
    </div>
  );
}
