import { Link } from "@tanstack/react-router";

import { useCurrentCourseQuery, useMeQuery } from "../shared/auth/session";

export function AccountPage() {
  const meQuery = useMeQuery();
  const currentCourseQuery = useCurrentCourseQuery();

  return (
    <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
      <section className="rounded-[1.75rem] border border-stone-200 bg-white p-6">
        <p className="font-mono text-[11px] text-stone-500 uppercase tracking-[0.35em]">Account</p>
        <h2 className="mt-3 font-semibold text-3xl text-stone-900">Profile</h2>
        {meQuery.data ? (
          <div className="mt-6 grid gap-4 text-sm text-stone-700">
            <div className="rounded-[1.25rem] bg-stone-50 px-4 py-4">
              <p className="text-stone-500 text-xs uppercase tracking-[0.25em]">Email</p>
              <p className="mt-2 text-base text-stone-900">{meQuery.data.email}</p>
            </div>
            <div className="rounded-[1.25rem] bg-stone-50 px-4 py-4">
              <p className="text-stone-500 text-xs uppercase tracking-[0.25em]">Plan</p>
              <p className="mt-2 text-base text-stone-900">
                {meQuery.data.has_pro_sub ? "Pro" : "Free"}
              </p>
            </div>
            <div className="rounded-[1.25rem] bg-stone-50 px-4 py-4">
              <p className="text-stone-500 text-xs uppercase tracking-[0.25em]">Role</p>
              <p className="mt-2 text-base text-stone-900">
                {meQuery.data.is_admin ? "Admin" : "Learner"}
              </p>
            </div>
          </div>
        ) : (
          <p className="mt-6 text-sm text-stone-600">Account details are unavailable.</p>
        )}
      </section>
      <section className="grid gap-6">
        <article className="rounded-[1.75rem] border border-stone-200 bg-white p-6">
          <p className="font-mono text-[11px] text-stone-500 uppercase tracking-[0.35em]">
            Active course
          </p>
          {currentCourseQuery.data ? (
            <div className="mt-6 grid gap-3 text-sm text-stone-700">
              <div className="rounded-[1.25rem] bg-stone-50 px-4 py-4">
                <p className="text-stone-500 text-xs uppercase tracking-[0.25em]">Code</p>
                <p className="mt-2 text-base text-stone-900">
                  {currentCourseQuery.data.course_code}
                </p>
              </div>
              <div className="rounded-[1.25rem] bg-stone-50 px-4 py-4">
                <p className="text-stone-500 text-xs uppercase tracking-[0.25em]">Version</p>
                <p className="mt-2 text-base text-stone-900">
                  {currentCourseQuery.data.course_version}
                </p>
              </div>
              <div className="rounded-[1.25rem] bg-stone-50 px-4 py-4">
                <p className="text-stone-500 text-xs uppercase tracking-[0.25em]">Status</p>
                <p className="mt-2 text-base text-stone-900">{currentCourseQuery.data.status}</p>
              </div>
              {currentCourseQuery.data.current_unit_id ? (
                <Link
                  className="mt-2 inline-flex w-fit rounded-full bg-stone-900 px-5 py-3 text-sm text-white transition hover:bg-stone-700"
                  params={{ unitId: currentCourseQuery.data.current_unit_id }}
                  to="/unit/$unitId"
                >
                  Open current unit
                </Link>
              ) : null}
            </div>
          ) : (
            <p className="mt-6 text-sm text-stone-600">No active course context found.</p>
          )}
        </article>
      </section>
    </div>
  );
}
