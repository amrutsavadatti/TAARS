/**
 * useSession — generates and persists a session ID in localStorage.
 *
 * Why localStorage?
 *   - Session IDs are not sensitive (no auth tokens here).
 *   - Persisting across page reloads means Valkey can recover the
 *     conversation history for returning visitors on the same browser.
 *   - When OTP is OFF we also store the visitor's email here so the
 *     identity gate form is pre-filled on return visits.
 */

const SESSION_KEY = "career_assistant_session_id";
const EMAIL_KEY = "career_assistant_visitor_email";
const NAME_KEY = "career_assistant_visitor_name";

/** Generate a UUID v4 (crypto.randomUUID preferred, fallback for older browsers) */
function generateId(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  // Fallback — good enough for a session identifier
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

/** Get (or create) the persistent session ID */
export function getSessionId(): string {
  try {
    const existing = localStorage.getItem(SESSION_KEY);
    if (existing) return existing;
    const id = generateId();
    localStorage.setItem(SESSION_KEY, id);
    return id;
  } catch {
    // localStorage blocked (private browsing, iframe sandbox) — use in-memory
    return generateId();
  }
}

/** Save visitor email for pre-fill (called after identity gate submission) */
export function saveVisitorEmail(email: string): void {
  try {
    localStorage.setItem(EMAIL_KEY, email);
  } catch {
    // ignore
  }
}

/** Get previously saved visitor email */
export function getSavedEmail(): string {
  try {
    return localStorage.getItem(EMAIL_KEY) ?? "";
  } catch {
    return "";
  }
}

/** Save visitor name */
export function saveVisitorName(name: string): void {
  try {
    localStorage.setItem(NAME_KEY, name);
  } catch {
    // ignore
  }
}

/** Get previously saved visitor name */
export function getSavedName(): string {
  try {
    return localStorage.getItem(NAME_KEY) ?? "";
  } catch {
    return "";
  }
}
