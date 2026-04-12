import { z } from "zod";

export const loginSchema = z.object({
  email: z.string().trim().email("Enter a valid email address.").max(200),
  password: z.string().trim().min(1, "Password is required.").max(200),
});

export type LoginFormValues = z.infer<typeof loginSchema>;
