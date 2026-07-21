import { expect, test } from "@playwright/test";

test("shorthand query returns a cited answer with the expected source", async ({ page }) => {
  await page.goto("/");
  await page.getByPlaceholder("terraform drift prod...").fill("terraform drift prod");
  await page.keyboard.press("Enter");

  await expect(page.getByText("Cited")).toBeVisible({ timeout: 15_000 });

  await page.getByText(/Sources \(\d+\)/).click();
  await expect(page.getByText(/Infrastructure\.md/)).toBeVisible();
});

test("a no-evidence query produces a stated limitation, not a fabricated claim", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByPlaceholder("terraform drift prod...")
    .fill("gibberish nonexistent topic xyzzy123");
  await page.keyboard.press("Enter");

  await expect(page.getByText("No grounding found")).toBeVisible({ timeout: 15_000 });
});
