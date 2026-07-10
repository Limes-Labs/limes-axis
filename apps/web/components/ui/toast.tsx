"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";
import Link from "next/link";
import { X } from "lucide-react";

import { cn } from "@/lib/cn";

/*
 * Lightweight toast system — React context + portal, no dependency. Toasts
 * stack bottom-right, auto-dismiss after 6 seconds and can be dismissed
 * manually. Optional link (e.g. to the audit event a decision created).
 */

export type ToastTone = "positive" | "danger" | "neutral";

export interface ToastInput {
  title: string;
  detail?: string;
  tone?: ToastTone;
  href?: string;
  hrefLabel?: string;
}

interface ToastRecord extends ToastInput {
  id: number;
}

interface ToastContextValue {
  push: (toast: ToastInput) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export const TOAST_DURATION_MS = 6000;

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within a <ToastProvider>.");
  }
  return context;
}

const toneClasses: Record<ToastTone, string> = {
  positive: "text-positive",
  danger: "text-danger",
  neutral: "text-signal",
};

function ToastCard({ toast, onDismiss }: { toast: ToastRecord; onDismiss: (id: number) => void }) {
  const { id } = toast;

  useEffect(() => {
    const timer = setTimeout(() => onDismiss(id), TOAST_DURATION_MS);
    return () => clearTimeout(timer);
  }, [id, onDismiss]);

  return (
    <div
      className={cn(
        "pointer-events-auto flex w-80 max-w-[calc(100vw-2rem)] items-start gap-2.5 rounded-2xl border border-line",
        "bg-surface p-4 shadow-[0_16px_44px_rgb(4_18_46/0.2)]",
        "dark:border-white/10 dark:shadow-[0_16px_44px_rgb(0_0_0/0.5)]",
      )}
      role="status"
    >
      <span
        aria-hidden="true"
        className={cn("status-dot mt-1.5", toneClasses[toast.tone ?? "neutral"])}
      />
      <div className="min-w-0 flex-1">
        <p className="m-0 text-sm font-medium break-words text-ink">{toast.title}</p>
        {toast.detail ? (
          <p className="mx-0 mt-0.5 mb-0 text-xs leading-snug break-words text-muted">
            {toast.detail}
          </p>
        ) : null}
        {toast.href ? (
          <Link
            className="mt-1.5 inline-flex text-xs font-medium text-signal hover:underline"
            href={toast.href}
          >
            {toast.hrefLabel ?? "View details"}
          </Link>
        ) : null}
      </div>
      <button
        aria-label="Dismiss notification"
        className="icon-button h-7 w-7 min-w-7 shrink-0"
        type="button"
        onClick={() => onDismiss(toast.id)}
      >
        <X aria-hidden="true" size={14} />
      </button>
    </div>
  );
}

export function ToastProvider({ children }: { children: ReactNode }) {
  // Toasts are only pushed from client-side interaction, so the portal never
  // renders during SSR/hydration — no mounted gate needed.
  const [toasts, setToasts] = useState<ToastRecord[]>([]);
  const nextIdRef = useRef(0);

  const dismiss = useCallback((id: number) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const push = useCallback((toast: ToastInput) => {
    const id = nextIdRef.current++;
    setToasts((current) => [...current, { ...toast, id }]);
  }, []);

  const contextValue = useMemo<ToastContextValue>(() => ({ push }), [push]);

  return (
    <ToastContext.Provider value={contextValue}>
      {children}
      {toasts.length > 0
        ? createPortal(
            <div
              aria-live="polite"
              className="pointer-events-none fixed right-4 bottom-4 z-[100] flex flex-col items-end gap-2"
            >
              {toasts.map((toast) => (
                <ToastCard key={toast.id} toast={toast} onDismiss={dismiss} />
              ))}
            </div>,
            document.body,
          )
        : null}
    </ToastContext.Provider>
  );
}
