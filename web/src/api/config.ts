// The API base is configurable so the same build can point at a remote Harness
// server over the user's secure network (SPEC/GITHUB_PAGES.md remote-client behavior).
const STORAGE_KEY = "harness.api_base";
const TOKEN_KEY = "harness.api_token";

export function getApiBase(): string {
  return localStorage.getItem(STORAGE_KEY) ?? "http://127.0.0.1:4096";
}

export function setApiBase(value: string): void {
  localStorage.setItem(STORAGE_KEY, value);
}

export function getApiToken(): string | undefined {
  // Session-only by default; SPEC/SECURITY_PRIVACY.md forbids secrets in localStorage.
  return sessionStorage.getItem(TOKEN_KEY) ?? undefined;
}

export function setApiToken(value: string): void {
  sessionStorage.setItem(TOKEN_KEY, value);
}
