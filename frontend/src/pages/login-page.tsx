import { useNavigate, useSearch } from "@tanstack/react-router";

import { LoginForm } from "../features/auth/login-form";
import { AuthPageShell } from "../features/auth/ui/auth-page-shell";

export function LoginPage() {
  const navigate = useNavigate();
  const search = useSearch({ from: "/login" });

  return (
    <AuthPageShell>
      <LoginForm
        onLoggedIn={async () => {
          await navigate({ to: search.redirect ?? "/path" });
        }}
        registerLinkSearch={search.redirect ? { redirect: search.redirect } : {}}
      />
    </AuthPageShell>
  );
}
