import { zodResolver } from "@hookform/resolvers/zod";
import { Link } from "@tanstack/react-router";
import { useId, useState } from "react";
import { useForm } from "react-hook-form";

import { getErrorMessage } from "../../shared/lib/api-error";
import { PRIMARY_BUTTON_CLASS } from "../../shared/ui/tokens/button-classes";
import {
  AUTH_ERROR_BANNER_CLASS,
  AUTH_FIELD_ERROR_CLASS,
  AUTH_ICON_BUTTON_CLASS,
  AUTH_INPUT_CLASS,
  AUTH_LABEL_TEXT_CLASS,
  AUTH_SUBTLE_LINK_CLASS,
} from "../../shared/ui/tokens/form-classes";
import { type LoginFormValues, loginSchema } from "./login-schema";
import { useLoginMutation } from "./mutations";
import { PasswordEyeIcon } from "./password-eye-icon";

type LoginFormProps = {
  onLoggedIn: () => void | Promise<void>;
  /** Forwarded to the register `Link` so redirect survives account creation. */
  registerLinkSearch: { redirect?: string };
};

export function LoginForm(props: LoginFormProps) {
  const { onLoggedIn, registerLinkSearch } = props;
  const loginMutation = useLoginMutation();
  const passwordId = useId();
  const [isPasswordVisible, setIsPasswordVisible] = useState(false);

  const form = useForm<LoginFormValues>({
    defaultValues: { email: "", password: "" },
    mode: "onChange",
    resolver: zodResolver(loginSchema),
  });

  const passwordError = form.formState.errors.password?.message;
  const emailError = form.formState.errors.email?.message;

  return (
    <section className="rounded-[1.6rem] border border-[var(--lesson-border)] bg-[var(--lesson-surface)] px-6 py-8 shadow-[0_12px_30px_rgba(22,28,37,0.045)] md:px-8 md:py-10">
      <h1 className="font-semibold text-3xl text-[var(--lesson-text)] tracking-[-0.03em]">
        Log in
      </h1>
      <p className="mt-2 text-[var(--lesson-text-muted)] text-sm leading-6">
        Continue your Japanese practice.
      </p>

      <form
        className="mt-7 grid gap-5"
        onSubmit={form.handleSubmit(async (values) => {
          await loginMutation.mutateAsync(values);
          await onLoggedIn();
        })}
      >
        <label className="grid gap-1.5">
          <span className={`font-medium ${AUTH_LABEL_TEXT_CLASS}`}>Email</span>
          <input
            className={AUTH_INPUT_CLASS}
            autoComplete="email"
            type="email"
            {...form.register("email")}
            aria-invalid={emailError ? "true" : "false"}
          />
          {emailError ? (
            <p className={AUTH_FIELD_ERROR_CLASS} role="alert">
              {emailError}
            </p>
          ) : null}
        </label>

        <label className="grid gap-1.5">
          <div className="flex items-center justify-between gap-3">
            <span className={`font-medium ${AUTH_LABEL_TEXT_CLASS}`}>Password</span>
            <a className={AUTH_SUBTLE_LINK_CLASS} href="/forgot-password">
              Forgot password?
            </a>
          </div>
          <div className="relative">
            <input
              className={`${AUTH_INPUT_CLASS} pr-11`}
              autoComplete="current-password"
              id={passwordId}
              type={isPasswordVisible ? "text" : "password"}
              {...form.register("password")}
              aria-invalid={passwordError ? "true" : "false"}
            />
            <button
              className={AUTH_ICON_BUTTON_CLASS}
              type="button"
              aria-label={isPasswordVisible ? "Hide password" : "Show password"}
              onClick={() => setIsPasswordVisible((v) => !v)}
            >
              <PasswordEyeIcon open={isPasswordVisible} />
            </button>
          </div>
          {passwordError ? (
            <p className={AUTH_FIELD_ERROR_CLASS} role="alert">
              {passwordError}
            </p>
          ) : null}
        </label>

        {loginMutation.error ? (
          <p className={AUTH_ERROR_BANNER_CLASS} role="alert">
            {getErrorMessage(loginMutation.error)}
          </p>
        ) : null}

        <button
          className={`${PRIMARY_BUTTON_CLASS} mt-2 w-full disabled:cursor-not-allowed disabled:opacity-70`}
          disabled={loginMutation.isPending || !form.formState.isValid}
          type="submit"
        >
          {loginMutation.isPending ? "Logging in..." : "Log in"}
        </button>

        <p className="mt-4 text-[var(--lesson-text-soft)] text-sm">
          Don&apos;t have an account?{" "}
          <Link
            className="font-medium text-[var(--lesson-accent)] underline underline-offset-4"
            search={registerLinkSearch}
            to="/register"
          >
            Create one
          </Link>
        </p>
      </form>
    </section>
  );
}
