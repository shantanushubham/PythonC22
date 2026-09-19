import { z } from "zod";

// Standard Indian IFSC format: 4 letters (bank code) + 0 + 6 alphanumeric (branch code)
const IFSC_REGEX = /^[A-Z]{4}0[A-Z0-9]{6}$/;

export const transactionSchema = z.object({
  accountNumber: z
    .string({ required_error: "accountNumber is required" })
    .trim()
    .regex(/^[0-9]{9,18}$/, "accountNumber must be numeric and 9-18 digits long"),
  ifsc: z
    .string({ required_error: "ifsc is required" })
    .trim()
    .toUpperCase()
    .regex(IFSC_REGEX, "ifsc must be a valid IFSC code (e.g. HDFC0001234)"),
  accountName: z
    .string({ required_error: "accountName is required" })
    .trim()
    .min(1, "accountName cannot be empty")
    .max(140, "accountName is too long"),
  bankName: z
    .string({ required_error: "bankName is required" })
    .trim()
    .min(1, "bankName cannot be empty")
    .max(140, "bankName is too long"),
  transactionType: z.enum(["credit", "debit"], {
    required_error: "transactionType is required",
    invalid_type_error: "transactionType must be either 'credit' or 'debit'",
  }),
  amount: z
    .number({ required_error: "amount is required", invalid_type_error: "amount must be a number" })
    .positive("amount must be greater than 0"),
});

export type TransactionInput = z.infer<typeof transactionSchema>;
