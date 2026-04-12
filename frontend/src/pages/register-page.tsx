import { useNavigate, useSearch } from "@tanstack/react-router";

import { RegisterForm } from "../features/auth/register-form";
import { AuthPageShell } from "../features/auth/ui/auth-page-shell";

export function RegisterPage() {
  const navigate = useNavigate();
  const search = useSearch({ from: "/register" });

  return (
    <AuthPageShell>
      <RegisterForm
        loginLinkSearch={search.redirect ? { redirect: search.redirect } : {}}
        onRegistered={async () => {
          await navigate({ to: search.redirect ?? "/path" });
        }}
      />
    </AuthPageShell>
  );
}
