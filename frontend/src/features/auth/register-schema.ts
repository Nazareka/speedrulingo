import { z } from "zod";

export const registerSchema = z
  .object({
    email: z.string().trim().email("Enter a valid email address.").max(200),
    password: z.string().trim().min(8, "Password must be at least 8 characters.").max(200),
    confirmPassword: z.string().trim(),
  })
  .refine((data) => data.password === data.confirmPassword, {
    path: ["confirmPassword"],
    message: "Passwords must match.",
  });

export type RegisterFormValues = z.infer<typeof registerSchema>;
