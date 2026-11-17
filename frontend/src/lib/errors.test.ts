import { describe, expect, it } from "vitest";
import { formatApiError } from "./errors.ts";

describe("formatApiError", () => {
  it("uses the envelope detail when there are no field errors", () => {
    const error = {
      message: "ignored",
      envelope: { code: "domain_error", detail: "Unknown option 'foo'" },
    };

    expect(formatApiError(error)).toBe("Unknown option 'foo'");
  });

  it("appends the field paths from the envelope errors", () => {
    const error = {
      message: "ignored",
      envelope: {
        code: "validation_error",
        detail: "The request body is invalid",
        errors: [
          { field: "content.subject", message: "Field required" },
          { field: "channels.0.recipients", message: "List should have at most 50 items" },
        ],
      },
    };

    expect(formatApiError(error)).toBe(
      "The request body is invalid (content.subject: Field required; channels.0.recipients: List should have at most 50 items)",
    );
  });

  it("falls back to a plain Error message", () => {
    expect(formatApiError(new Error("Network down"))).toBe("Network down");
  });

  it("falls back to a string for an unknown value", () => {
    expect(formatApiError("boom")).toBe("boom");
  });
});
