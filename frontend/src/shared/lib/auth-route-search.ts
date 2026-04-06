import { z } from "zod";

/** Login/register URL search: optional in-app redirect (blocks open redirects). */
export const authRouteSearchSchema = z.object({
  redirect: z
    .string()
    .optional()
    .refine((s) => !s || (s.startsWith("/") && !s.startsWith("//")), {
      message: "Invalid redirect",
    }),
});
