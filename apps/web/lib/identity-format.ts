import type { IdentitySessionReadModel } from "./platform-overview";

export function apiStatusClass(state: string): string {
  if (state === "online") {
    return "signal-ready";
  }

  if (state === "degraded" || state === "checking") {
    return "signal-watch";
  }

  return "signal-action-required";
}

export function compactActorLabel(actorId: string): string {
  return actorId.length > 30 ? `${actorId.slice(0, 27)}...` : actorId;
}

export function operatorInitials(actorId?: string): string {
  if (!actorId) {
    return "OP";
  }

  const parts = actorId
    .split(/[^a-zA-Z0-9]+/)
    .map((part) => part.trim())
    .filter(Boolean);
  const letters = (parts.length > 1 ? [parts[0], parts[1]] : [actorId.slice(0, 2)])
    .map((part) => part[0]?.toUpperCase())
    .join("");

  return letters || "OP";
}

export function formatExpiry(expiresAt?: number): string {
  if (!expiresAt) {
    return "Not provided";
  }

  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(expiresAt * 1000));
}

export function notificationTone(severity: string): string {
  if (severity === "ready") {
    return "signal-ready";
  }

  return severity === "watch" ? "signal-watch" : "signal-action-required";
}

export function identitySessionLabel(
  identitySession: IdentitySessionReadModel | null,
): string {
  if (!identitySession) {
    return "API required";
  }

  return identitySession.authenticated ? "API verified" : "Public";
}

export function identitySessionTone(
  identitySession: IdentitySessionReadModel | null,
): string {
  if (!identitySession) {
    return "signal-action-required";
  }

  if (identitySession.authenticated) {
    return "signal-ready";
  }

  return identitySession.api_auth_required ? "signal-action-required" : "signal-watch";
}
