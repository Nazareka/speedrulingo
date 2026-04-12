import { zodResolver } from "@hookform/resolvers/zod";
import { Link } from "@tanstack/react-router";
import { useId, useState } from "react";
import { useForm } from "react-hook-form";

import { getErrorMessage } from "../../shared/lib/api-error";
import { PRIMARY_BUTTON_CLASS } from "../../shared/ui/tokens/button-classes";
import {
  AUTH_ERROR_BANNER_CLASS,
  AUTH_FIELD_ERROR_CLASS,
  AUTH_HELPER_TEXT_CLASS,
  AUTH_ICON_BUTTON_CLASS,
  AUTH_INPUT_CLASS,
  AUTH_LABEL_TEXT_CLASS,
} from "../../shared/ui/tokens/form-classes";
import { useRegisterMutation } from "./mutations";
import { PasswordEyeIcon } from "./password-eye-icon";
import { type RegisterFormValues, registerSchema } from "./register-schema";

type RegisterFormProps = {
  onRegistered: () => void | Promise<void>;
  loginLinkSearch: { redirect?: string };
};

export function RegisterForm(props: RegisterFormProps) {
  const { onRegistered, loginLinkSearch } = props;
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
          await onRegistered();
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
              <PasswordEyeIcon open={isPasswordVisible} />
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
              <PasswordEyeIcon open={isConfirmPasswordVisible} />
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
            search={loginLinkSearch}
            to="/login"
          >
            Log in
          </Link>
        </p>
      </form>
    </section>
  );
}
