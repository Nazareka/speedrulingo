import { zodResolver } from "@hookform/resolvers/zod";
import { Link, useNavigate } from "@tanstack/react-router";
import { useId, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { useRegisterMutation } from "../features/auth/mutations";
import { getErrorMessage } from "../shared/lib/api-error";
import {
  AUTH_ERROR_BANNER_CLASS,
  AUTH_FIELD_ERROR_CLASS,
  AUTH_HELPER_TEXT_CLASS,
  AUTH_ICON_BUTTON_CLASS,
  AUTH_INPUT_CLASS,
  AUTH_LABEL_TEXT_CLASS,
  PRIMARY_BUTTON_CLASS,
} from "../shared/ui/auth/auth-classes";

const registerSchema = z
  .object({
    email: z.string().trim().email("Enter a valid email address.").max(200),
    password: z.string().trim().min(8, "Password must be at least 8 characters.").max(200),
    confirmPassword: z.string().trim(),
  })
  .refine((data) => data.password === data.confirmPassword, {
    path: ["confirmPassword"],
    message: "Passwords must match.",
  });

type RegisterFormValues = z.infer<typeof registerSchema>;

function EyeIcon(props: { open: boolean }) {
  const { open } = props;

  return open ? (
    <svg
      aria-hidden="true"
      fill="none"
      height="18"
      viewBox="0 0 24 24"
      width="18"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        d="M2.5 12s3.5-7 9.5-7 9.5 7 9.5 7-3.5 7-9.5 7-9.5-7-9.5-7Z"
        stroke="currentColor"
        strokeWidth="1.7"
      />
      <path
        d="M12 15.2a3.2 3.2 0 1 0 0-6.4 3.2 3.2 0 0 0 0 6.4Z"
        stroke="currentColor"
        strokeWidth="1.7"
      />
    </svg>
  ) : (
    <svg
      aria-hidden="true"
      fill="none"
      height="18"
      viewBox="0 0 24 24"
      width="18"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path d="M4 4l16 16" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
      <path
        d="M10.6 10.6A2.7 2.7 0 0 0 12 15.2c1.5 0 2.7-1.2 2.7-2.7 0-.5-.1-1-.4-1.4"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
      />
      <path
        d="M3.2 12s3.3-6.6 8.8-6.6c2 0 3.6.7 4.9 1.7M20.8 12s-3.3 6.6-8.8 6.6c-2 0-3.6-.7-4.9-1.7"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function RegisterPage() {
  const navigate = useNavigate();
  const registerMutation = useRegisterMutation();
  const passwordId = useId();
  const confirmPasswordId = useId();
  const [isPasswordVisible, setIsPasswordVisible] = useState(false);
  const [isConfirmPasswordVisible, setIsConfirmPasswordVisible] = useState(false);

  const form = useForm<RegisterFormValues>({
    defaultValues: { email: "", password: "", confirmPassword: "" },
    mode: "onChange",
    resolver: zodResolver(registerSchema),
  });

  const emailError = form.formState.errors.email?.message;
  const passwordError = form.formState.errors.password?.message;
  const confirmPasswordError = form.formState.errors.confirmPassword?.message;

  return (
    <div className="min-h-screen bg-[var(--lesson-bg)] font-['Inter','SF_Pro_Display','SF_Pro_Text','Geist',system-ui,sans-serif] text-[var(--lesson-text)]">
      <main className="mx-auto max-w-5xl px-4 pt-12 pb-12 md:px-6 md:pt-14">
        <div className="mx-auto w-full max-w-[500px]">
          <header className="mb-7">
            <p className="font-mono text-[11px] text-[var(--lesson-text-faint)] uppercase tracking-[0.35em]">
              SPEEDRULINGO
            </p>
            <p className="mt-2 text-[var(--lesson-text-muted)] text-sm">
              Japanese practice, one unit at a time.
            </p>
          </header>

          <section className="rounded-[1.6rem] border border-[var(--lesson-border)] bg-[var(--lesson-surface)] px-6 py-8 shadow-[0_12px_30px_rgba(22,28,37,0.045)] md:px-8 md:py-10">
            <h1 className="font-semibold text-3xl text-[var(--lesson-text)] tracking-[-0.03em]">
              Create account
            </h1>
            <p className="mt-2 text-[var(--lesson-text-muted)] text-sm leading-6">
              Start your path and keep your progress.
            </p>

            <form
              className="mt-7 grid gap-5"
              onSubmit={form.handleSubmit(async (formValues) => {
                await registerMutation.mutateAsync({
                  email: formValues.email,
                  password: formValues.password,
                });
                await navigate({ to: "/path" });
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
                <span className={`font-medium ${AUTH_LABEL_TEXT_CLASS}`}>Password</span>
                <div className="relative">
                  <input
                    className={`${AUTH_INPUT_CLASS} pr-11`}
                    autoComplete="new-password"
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
                    <EyeIcon open={isPasswordVisible} />
                  </button>
                </div>
                {passwordError ? (
                  <p className={AUTH_FIELD_ERROR_CLASS} role="alert">
                    {passwordError}
                  </p>
                ) : null}
                <p className={AUTH_HELPER_TEXT_CLASS}>Minimum 8 characters. Max 200.</p>
              </label>

              <label className="grid gap-1.5">
                <span className={`font-medium ${AUTH_LABEL_TEXT_CLASS}`}>Confirm password</span>
                <div className="relative">
                  <input
                    className={`${AUTH_INPUT_CLASS} pr-11`}
                    autoComplete="new-password"
                    id={confirmPasswordId}
                    type={isConfirmPasswordVisible ? "text" : "password"}
                    {...form.register("confirmPassword")}
                    aria-invalid={confirmPasswordError ? "true" : "false"}
                  />
                  <button
                    className={AUTH_ICON_BUTTON_CLASS}
                    type="button"
                    aria-label={isConfirmPasswordVisible ? "Hide password" : "Show password"}
                    onClick={() => setIsConfirmPasswordVisible((v) => !v)}
                  >
                    <EyeIcon open={isConfirmPasswordVisible} />
                  </button>
                </div>
                {confirmPasswordError ? (
                  <p className={AUTH_FIELD_ERROR_CLASS} role="alert">
                    {confirmPasswordError}
                  </p>
                ) : null}
              </label>

              {registerMutation.error ? (
                <p className={AUTH_ERROR_BANNER_CLASS} role="alert">
                  {getErrorMessage(registerMutation.error)}
                </p>
              ) : null}

              <button
                className={`${PRIMARY_BUTTON_CLASS} mt-2 w-full disabled:cursor-not-allowed disabled:opacity-70`}
                disabled={registerMutation.isPending || !form.formState.isValid}
                type="submit"
              >
                {registerMutation.isPending ? "Creating..." : "Create account"}
              </button>

              <p className="mt-4 text-[var(--lesson-text-soft)] text-sm">
                Already have an account?{" "}
                <Link
                  className="font-medium text-[var(--lesson-accent)] underline underline-offset-4"
                  to="/login"
                >
                  Log in
                </Link>
              </p>
            </form>
          </section>
        </div>
      </main>
    </div>
  );
}
