import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";
export default defineConfig({resolve:{alias:{"@":fileURLToPath(new URL("./src",import.meta.url))}},test:{env:{NEXT_PUBLIC_API_ORIGIN:"http://localhost:8000"},include:["src/**/*.test.ts"],environment:"node"}});
