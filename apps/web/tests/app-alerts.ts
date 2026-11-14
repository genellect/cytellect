import type {Page} from "@playwright/test";

/**
 * The application's own alerts. Next.js adds a role="alert" route announcer (#__next-route-announcer__) to the page,
 * so page.getByRole("alert") can match two elements and fail in strict mode depending on when the announcer appears.
 * Application messages can sit inside or outside <main>, so exclude the announcer instead of narrowing the region.
 */
export function appAlerts(page: Page) {
  return page.getByRole("alert").and(page.locator(":not(#__next-route-announcer__)"));
}
