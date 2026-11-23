import { z } from 'zod';

export const AnalyzeRequestSchema = z.object({
  scenario_id: z
    .string()
    .trim()
    .min(1, 'scenario_id is required')
    .max(128, 'scenario_id must be at most 128 characters')
    .regex(/^[a-zA-Z0-9_-]+$/, 'scenario_id must contain only letters, digits, underscores, or hyphens'),
  doc_id: z
    .string()
    .trim()
    .min(1)
    .max(256, 'doc_id must be at most 256 characters')
    .optional(),
  prompt: z
    .string()
    .trim()
    .min(5, 'prompt must be at least 5 characters')
    .max(4000, 'prompt must be at most 4000 characters'),
  persist_report: z.boolean().optional().default(true),
  document_text: z.preprocess(
    (value) => (typeof value === 'string' && value.trim() === '' ? undefined : value),
    z.string().trim().max(20_000, 'document_text must be at most 20,000 characters (public demo limit)').optional(),
  ),
});

export type ValidatedAnalyzeRequest = z.infer<typeof AnalyzeRequestSchema>;

export function formatZodErrors(error: z.ZodError): Record<string, string[] | undefined> {
  return z.flattenError(error).fieldErrors;
}
