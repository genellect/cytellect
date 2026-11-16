import { describe, expect, it } from "vitest";
import { storeDestination } from "./StoreLink";

const links = { app: "ms-windows-store://pdp/?ProductId=9PGKTQGV7X5C", web: "https://apps.microsoft.com/detail/9PGKTQGV7X5C" };

describe("the Store button's destination", () => {
  it("opens the Store app on Windows", () => {
    expect(storeDestination("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", links)).toBe(links.app);
  });
  it("opens the web listing where the Store app link has no handler", () => {
    for (const agent of ["Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)", "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X)",
      "Mozilla/5.0 (Linux; Android 15)", "Mozilla/5.0 (X11; Linux x86_64)"]) expect(storeDestination(agent, links)).toBe(links.web);
  });
});
