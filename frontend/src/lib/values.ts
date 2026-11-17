// Small value parsers shared by the send form and the channel editor, so the two places that
// coerce the same option shapes cannot drift.

const NUMERIC = /^\d+$/;

/** A numeric priority becomes a number; an alias (`urgent`, …) stays a string for the server. */
export function parsePriority(value: string): number | string | undefined {
  const trimmed = value.trim();
  if (trimmed === "") return undefined;
  return NUMERIC.test(trimmed) ? Number(trimmed) : trimmed;
}

/** Splits a comma-separated field into trimmed, non-empty values. */
export function splitCommaList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter((item) => item !== "");
}
