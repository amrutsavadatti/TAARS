/**
 * useSSE — SSE streaming hook for the chat endpoint.
 *
 * Why EventSource instead of fetch + ReadableStream?
 *   - EventSource handles reconnection automatically.
 *   - Named events (event: rate_limit, event: identity_gate) are parsed
 *     natively — we get the event type and data in separate callbacks.
 *   - Works in every modern browser with no polyfill.
 *
 * Named SSE events we handle:
 *   (unnamed) data: "token"   → regular response token, append to message
 *   event: rate_limit         → visitor hit daily limit, show rate-limit screen
 *   event: identity_gate      → OTP gate triggered, show identity form
 *   data: [DONE]              → stream complete
 */

import { useState, useRef, useCallback } from "react";

export type SSEState = "idle" | "streaming" | "done" | "error";

export interface GatePayload {
  reason: "rate_limit" | "identity_gate";
  /** For rate_limit: "Come back tomorrow" message from server */
  message?: string;
  /** Cal.com booking URL */
  cal_url?: string;
  /** Owner contact email */
  contact_email?: string;
  /** Questions answered so far (for identity_gate) */
  questions_answered?: number;
}

export interface AnswerEvidence {
  source_type: string;
  source_id: string;
  title: string;
  quote: string;
}

export interface AnswerMetadata {
  status: "SUPPORTED" | "PARTIAL" | "UNANSWERABLE";
  evidence: AnswerEvidence[];
  snapshot_version: number;
  knowledge_backend: string;
  knowledge_backend_version: string;
}

interface UseSSEOptions {
  apiKey: string;
  baseUrl: string;
  sessionId: string;
  /** Called for each token as it arrives */
  onToken: (token: string) => void;
  /** Called when stream is complete */
  onDone: () => void;
  /** Called when a named gate event arrives */
  onGate: (payload: GatePayload) => void;
  /** Called once retrieval and grounding metadata is available */
  onMetadata: (payload: AnswerMetadata) => void;
  /** Called on network/parse errors */
  onError: (msg: string) => void;
}

export function useSSE(opts: UseSSEOptions) {
  const [state, setState] = useState<SSEState>("idle");
  const esRef = useRef<EventSource | null>(null);

  const send = useCallback(
    (question: string, visitorEmail?: string, visitorName?: string) => {
      // Close any existing connection
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }

      setState("streaming");

      // Build query string
      const params = new URLSearchParams({
        q: question,
        session_id: opts.sessionId,
      });
      if (visitorEmail) params.set("visitor_email", visitorEmail);
      if (visitorName) params.set("visitor_name", visitorName);

      const url = `${opts.baseUrl}/api/v1/chat/stream?${params.toString()}`;

      // EventSource doesn't support custom headers natively.
      // We pass the API key as a query parameter (the backend reads it from
      // either X-API-Key header or ?api_key= query param).
      const urlWithKey = `${url}&api_key=${encodeURIComponent(opts.apiKey)}`;
      const es = new EventSource(urlWithKey);
      esRef.current = es;

      // --- Default (unnamed) events — regular tokens ---
      es.onmessage = (event: MessageEvent) => {
        const raw: string = event.data;
        if (raw === "[DONE]") {
          es.close();
          esRef.current = null;
          setState("done");
          opts.onDone();
          return;
        }
        try {
          // Server sends JSON-encoded strings: data: "token"
          const token = JSON.parse(raw) as string;
          opts.onToken(token);
        } catch {
          // plain string fallback
          opts.onToken(raw);
        }
      };

      // --- Named event: rate_limit ---
      es.addEventListener("rate_limit", (event: Event) => {
        const me = event as MessageEvent;
        es.close();
        esRef.current = null;
        setState("done");
        try {
          const payload = JSON.parse(me.data) as GatePayload;
          opts.onGate({ ...payload, reason: "rate_limit" });
        } catch {
          opts.onGate({ reason: "rate_limit" });
        }
      });

      // --- Named event: identity_gate ---
      es.addEventListener("identity_gate", (event: Event) => {
        const me = event as MessageEvent;
        es.close();
        esRef.current = null;
        setState("done");
        try {
          const payload = JSON.parse(me.data) as GatePayload;
          opts.onGate({ ...payload, reason: "identity_gate" });
        } catch {
          opts.onGate({ reason: "identity_gate" });
        }
      });

      es.addEventListener("answer_metadata", (event: Event) => {
        const me = event as MessageEvent;
        try {
          opts.onMetadata(JSON.parse(me.data) as AnswerMetadata);
        } catch {
          opts.onError("The assistant returned invalid evidence metadata.");
          es.close();
          esRef.current = null;
          setState("error");
        }
      });

      // --- Network / server errors ---
      es.onerror = () => {
        es.close();
        esRef.current = null;
        setState("error");
        opts.onError("Connection error — please try again.");
      };
    },
    [opts]
  );

  const abort = useCallback(() => {
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }
    setState("idle");
  }, []);

  return { state, send, abort };
}
