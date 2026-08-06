import { expect, test } from "@playwright/test";

// Proves the Phase-4 vertical slice end-to-end in a real browser against a running
// Harness server: bootstrap a contact/session, send a mentioned message, see the
// deterministic fake-provider reply rendered (SPEC/DEFINITION_OF_DONE.md item 13).
test("chat displays a live conversation against the real API", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });

  await page.goto("/");
  await expect(page.getByText("@builder")).toBeVisible({ timeout: 10000 });

  await page.getByLabel("Message").fill("@builder hello from playwright");
  await page.getByRole("button", { name: "Send" }).click();

  await expect(page.getByText("hello from playwright")).toBeVisible();
  await expect(page.locator(".message-author", { hasText: "builder" })).toBeVisible({
    timeout: 10000,
  });

  expect(consoleErrors).toEqual([]);
});
