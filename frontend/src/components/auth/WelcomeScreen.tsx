"use client";

import { useState, type FormEvent } from "react";
import { Sparkles } from "lucide-react";
import { useUser } from "@/context/UserContext";
import { dictionaries } from "@/locales";

const SESSION_FIELD_NAME = "sessionId" as const;

const t = dictionaries.welcomeScreen;
const tErrors = dictionaries.errors;

function getSessionIdFromForm(form: HTMLFormElement): string {
  const formData = new FormData(form);
  const raw = formData.get(SESSION_FIELD_NAME);
  if (typeof raw !== "string") {
    return "";
  }
  return raw.trim();
}

export function WelcomeScreen() {
  const { login } = useUser();
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    const value = getSessionIdFromForm(event.currentTarget);

    try {
      login(value);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : tErrors.welcomeFallback);
    }
  };

  const errorId = "welcome-session-error";
  const hintId = "welcome-session-hint";
  const titleId = "welcome-title";
  const inputDescribedBy = error
    ? `${hintId} ${errorId}`
    : hintId;

  return (
    <div
      className="min-h-screen w-full bg-gray-50 flex items-center justify-center p-4"
      role="main"
      aria-labelledby={titleId}
    >
      <div className="bg-white shadow-xl rounded-2xl p-8 w-full max-w-md border border-gray-100">
        <div className="flex justify-center mb-6" aria-hidden="true">
          <div className="p-3 rounded-xl bg-emerald-500 text-white">
            <Sparkles className="w-10 h-10" aria-hidden="true" focusable="false" />
          </div>
        </div>
        <h1
          id={titleId}
          className="text-2xl font-bold text-gray-800 text-center mb-2"
        >
          {t.title}
        </h1>
        <p className="text-gray-500 text-center text-sm mb-6">
          {t.subtitle}
        </p>
        <form
          onSubmit={handleSubmit}
          className="space-y-4"
          aria-label={t.formAriaLabel}
          noValidate
        >
          <label htmlFor={SESSION_FIELD_NAME} className="block">
            <span className="sr-only">{t.inputLabel}</span>
            <input
              id={SESSION_FIELD_NAME}
              type="text"
              name={SESSION_FIELD_NAME}
              placeholder={t.inputPlaceholder}
              autoComplete="username"
              required
              aria-required="true"
              aria-invalid={error ? "true" : "false"}
              aria-describedby={inputDescribedBy}
              className="w-full px-4 py-3 rounded-xl border border-gray-200 bg-gray-50 text-gray-800 placeholder:text-gray-400 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-500"
            />
          </label>
          {error && (
            <div
              id={errorId}
              role="alert"
              aria-live="polite"
              className="rounded-lg border border-red-200 bg-red-50 text-red-800 px-3 py-2 text-xs"
            >
              {error}
            </div>
          )}
          <button
            type="submit"
            aria-label={t.submitAriaLabel}
            className="w-full py-3 rounded-xl bg-emerald-500 text-white font-semibold text-sm hover:bg-emerald-600 transition-colors"
          >
            {t.submitButton}
          </button>
        </form>
        <p
          id={hintId}
          className="text-gray-400 text-xs text-center mt-4"
        >
          {t.hint}
        </p>
      </div>
    </div>
  );
}
