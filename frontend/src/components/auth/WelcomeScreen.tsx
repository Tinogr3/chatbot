"use client";

import { useState, type FormEvent } from "react";
import { Eye, EyeOff, Sparkles } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { dictionaries } from "@/locales";

type Mode = "login" | "register";

const tL = dictionaries.authScreen.login;
const tR = dictionaries.authScreen.register;

// ---------------------------------------------------------------------------
// Campo con botón de mostrar/ocultar contraseña
// ---------------------------------------------------------------------------
function PasswordField({
  id,
  name,
  placeholder,
  label,
  autoComplete,
  value,
  onChange,
  describedBy,
  invalid,
}: {
  id: string;
  name: string;
  placeholder: string;
  label: string;
  autoComplete: string;
  value: string;
  onChange: (v: string) => void;
  describedBy?: string;
  invalid?: boolean;
}) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="relative">
      <span className="sr-only">
        <label htmlFor={id}>{label}</label>
      </span>
      <input
        id={id}
        name={name}
        type={visible ? "text" : "password"}
        autoComplete={autoComplete}
        placeholder={placeholder}
        required
        aria-required="true"
        aria-invalid={invalid ? "true" : "false"}
        aria-describedby={describedBy}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full px-4 py-3 pr-11 rounded-xl border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-gray-800 dark:text-gray-100 placeholder:text-gray-400 dark:placeholder:text-gray-500 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-500"
      />
      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        aria-label={visible ? "Ocultar contraseña" : "Mostrar contraseña"}
        className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
      >
        {visible ? (
          <EyeOff className="w-4 h-4" aria-hidden />
        ) : (
          <Eye className="w-4 h-4" aria-hidden />
        )}
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Pantalla de login
// ---------------------------------------------------------------------------
function LoginForm({ onSwitchToRegister }: { onSwitchToRegister: () => void }) {
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const errorId = "login-error";

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(username.trim().toLowerCase(), password);
    } catch (err) {
      setError(err instanceof Error ? err.message : tL.submitButton);
    } finally {
      setLoading(false);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="space-y-3"
      aria-label={tL.formAriaLabel}
      noValidate
    >
      <div>
        <span className="sr-only">
          <label htmlFor="login-username">{tL.usernameLabel}</label>
        </span>
        <input
          id="login-username"
          type="text"
          name="username"
          autoComplete="username"
          placeholder={tL.usernamePlaceholder}
          required
          aria-required="true"
          aria-invalid={error ? "true" : "false"}
          aria-describedby={error ? errorId : undefined}
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          className="w-full px-4 py-3 rounded-xl border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-gray-800 dark:text-gray-100 placeholder:text-gray-400 dark:placeholder:text-gray-500 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-500"
        />
      </div>

      <PasswordField
        id="login-password"
        name="password"
        placeholder={tL.passwordPlaceholder}
        label={tL.passwordLabel}
        autoComplete="current-password"
        value={password}
        onChange={setPassword}
        describedBy={error ? errorId : undefined}
        invalid={!!error}
      />

      {error && (
        <div
          id={errorId}
          role="alert"
          aria-live="polite"
          className="rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/30 text-red-800 dark:text-red-200 px-3 py-2 text-xs"
        >
          {error}
        </div>
      )}

      <button
        type="submit"
        disabled={loading}
        aria-label={tL.submitAriaLabel}
        className="w-full py-3 rounded-xl bg-emerald-500 text-white font-semibold text-sm hover:bg-emerald-600 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
      >
        {loading ? "Entrando…" : tL.submitButton}
      </button>

      <button
        type="button"
        onClick={onSwitchToRegister}
        className="w-full text-center text-xs text-emerald-600 dark:text-emerald-400 hover:underline pt-1"
      >
        {tL.registerLink}
      </button>

      <p className="text-gray-400 dark:text-gray-500 text-xs text-center">
        {tL.forgotHint}
      </p>
    </form>
  );
}

// ---------------------------------------------------------------------------
// Pantalla de registro
// ---------------------------------------------------------------------------
function RegisterForm({ onSwitchToLogin }: { onSwitchToLogin: () => void }) {
  const { register } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [role, setRole] = useState<"ALUMNO" | "FORMADOR">("ALUMNO");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const errorId = "register-error";

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError(null);

    if (password !== confirmPassword) {
      setError(tR.passwordMismatch);
      return;
    }

    setLoading(true);
    try {
      await register(
        username.trim().toLowerCase(),
        password,
        role === "FORMADOR" ? "formador" : "alumno",
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al crear la cuenta.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="space-y-3"
      aria-label={tR.formAriaLabel}
      noValidate
    >
      <div>
        <span className="sr-only">
          <label htmlFor="reg-username">{tR.usernameLabel}</label>
        </span>
        <input
          id="reg-username"
          type="text"
          name="username"
          autoComplete="username"
          placeholder={tR.usernamePlaceholder}
          required
          aria-required="true"
          aria-invalid={error ? "true" : "false"}
          aria-describedby={`reg-username-hint${error ? ` ${errorId}` : ""}`}
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          className="w-full px-4 py-3 rounded-xl border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-gray-800 dark:text-gray-100 placeholder:text-gray-400 dark:placeholder:text-gray-500 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-500"
        />
        <p id="reg-username-hint" className="mt-1 text-xs text-gray-400 dark:text-gray-500 pl-1">
          {tR.usernameHint}
        </p>
      </div>

      <div>
        <PasswordField
          id="reg-password"
          name="password"
          placeholder={tR.passwordPlaceholder}
          label={tR.passwordLabel}
          autoComplete="new-password"
          value={password}
          onChange={setPassword}
          describedBy={`reg-password-hint${error ? ` ${errorId}` : ""}`}
          invalid={!!error}
        />
        <p id="reg-password-hint" className="mt-1 text-xs text-gray-400 dark:text-gray-500 pl-1">
          {tR.passwordHint}
        </p>
      </div>

      <PasswordField
        id="reg-confirm-password"
        name="confirmPassword"
        placeholder={tR.confirmPasswordPlaceholder}
        label={tR.confirmPasswordLabel}
        autoComplete="new-password"
        value={confirmPassword}
        onChange={setConfirmPassword}
        describedBy={error ? errorId : undefined}
        invalid={!!error}
      />

      <fieldset className="space-y-2">
        <legend className="text-xs font-medium text-gray-600 dark:text-gray-300">
          {tR.roleLabel}
        </legend>
        <div
          className="grid grid-cols-2 gap-2 rounded-xl bg-gray-100 p-1 dark:bg-gray-800"
          role="radiogroup"
          aria-label={tR.roleLabel}
        >
          {(
            [
              { value: "ALUMNO" as const, label: tR.roleStudent },
              { value: "FORMADOR" as const, label: tR.roleTrainer },
            ] as const
          ).map((option) => {
            const selected = role === option.value;
            return (
              <label
                key={option.value}
                className={`cursor-pointer rounded-lg px-3 py-2.5 text-center text-sm font-medium transition-colors ${
                  selected
                    ? "bg-emerald-500 text-white shadow-sm"
                    : "text-gray-600 hover:text-gray-800 dark:text-gray-300 dark:hover:text-gray-100"
                }`}
              >
                <input
                  type="radio"
                  name="role"
                  value={option.value}
                  checked={selected}
                  onChange={() => setRole(option.value)}
                  className="sr-only"
                />
                {option.label}
              </label>
            );
          })}
        </div>
      </fieldset>

      {error && (
        <div
          id={errorId}
          role="alert"
          aria-live="polite"
          className="rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/30 text-red-800 dark:text-red-200 px-3 py-2 text-xs"
        >
          {error}
        </div>
      )}

      <button
        type="submit"
        disabled={loading}
        aria-label={tR.submitAriaLabel}
        className="w-full py-3 rounded-xl bg-emerald-500 text-white font-semibold text-sm hover:bg-emerald-600 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
      >
        {loading ? "Creando cuenta…" : tR.submitButton}
      </button>

      <button
        type="button"
        onClick={onSwitchToLogin}
        className="w-full text-center text-xs text-emerald-600 dark:text-emerald-400 hover:underline pt-1"
      >
        {tR.loginLink}
      </button>
    </form>
  );
}

// ---------------------------------------------------------------------------
// Componente principal
// ---------------------------------------------------------------------------
export function WelcomeScreen() {
  const [mode, setMode] = useState<Mode>("login");
  const titleId = "auth-title";

  const t = mode === "login" ? tL : tR;

  return (
    <div
      className="min-h-screen w-full bg-gray-50 dark:bg-gray-950 flex items-center justify-center p-4"
      role="main"
      aria-labelledby={titleId}
    >
      <div className="bg-white dark:bg-gray-900 shadow-xl rounded-2xl p-8 w-full max-w-md border border-gray-100 dark:border-gray-800">
        {/* Logo */}
        <div className="flex justify-center mb-6" aria-hidden="true">
          <div className="p-3 rounded-xl bg-emerald-500 text-white">
            <Sparkles className="w-10 h-10" aria-hidden focusable="false" />
          </div>
        </div>

        {/* Título dinámico */}
        <h1
          id={titleId}
          className="text-2xl font-bold text-gray-800 dark:text-gray-100 text-center mb-1"
        >
          {t.title}
        </h1>
        <p className="text-gray-500 dark:text-gray-400 text-center text-sm mb-6">
          {t.subtitle}
        </p>

        {/* Formulario según modo */}
        {mode === "login" ? (
          <LoginForm onSwitchToRegister={() => setMode("register")} />
        ) : (
          <RegisterForm onSwitchToLogin={() => setMode("login")} />
        )}
      </div>
    </div>
  );
}
