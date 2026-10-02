import { defineConfig } from "vitest/config";
export default defineConfig({test:{env:{NEXT_PUBLIC_API_ORIGIN:"http://localhost:8000"},include:["src/**/*.test.ts"],environment:"node"}});
