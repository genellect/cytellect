import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTypescript from "eslint-config-next/typescript";
export default defineConfig([...nextVitals, ...nextTypescript, { rules: { "react-hooks/set-state-in-effect": "off", "@next/next/no-img-element": "off" } }, { files: ["tests/**/*.ts"], rules: { "no-restricted-syntax": ["error", {
  // Next.js adds its own role="alert" route announcer to the page, so a page-wide alert locator can match two
  // elements and fail in strict mode depending on when the announcer appears (tests/app-alerts.ts).
  selector: 'CallExpression[callee.type="MemberExpression"][callee.object.name="page"][callee.property.name="getByRole"][arguments.length=1][arguments.0.value="alert"]:not(MemberExpression[property.name=/^(filter|and)$/] > CallExpression)',
  message: 'page.getByRole("alert") also matches the Next.js route announcer. Use appAlerts(page) from tests/app-alerts.ts, or filter by the message text.',
}] } }, globalIgnores([".next/**", ".next-connected-acceptance/**", "next-env.d.ts", "test-results/**", "playwright-report/**", "src/lib/generated.ts"])]);
