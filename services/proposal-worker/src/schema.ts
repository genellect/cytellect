/** Validator for the closed, generated proposal schema. Not a general JSON Schema engine.
 * No coercion, defaults, remote refs or unregistered extensions. Semantics stay local.
 */
type Schema = Record<string, unknown>;
const annotations = new Set(["title", "description", "default", "$defs"]);
const supported = new Set(["$ref", "type", "anyOf", "enum", "const", "properties", "required", "additionalProperties", "items", "minItems", "maxItems", "minimum", "maximum", "minLength", "maxLength", "pattern"]);

export function matchesSchema(value: unknown, raw: unknown, root: unknown = raw, depth = 0): boolean {
  if (depth > 30 || !raw || typeof raw !== "object" || Array.isArray(raw)) return false;
  const schema = raw as Schema;
  if (Object.keys(schema).some((key) => !annotations.has(key) && !supported.has(key))) return false;
  if (typeof schema.$ref === "string") {
    const match = /^#\/\$defs\/([A-Za-z0-9_]+)$/.exec(schema.$ref);
    const definitions = (root as Schema).$defs as Schema | undefined;
    return !!match && matchesSchema(value, definitions?.[match[1]], root, depth + 1);
  }
  if (Array.isArray(schema.anyOf) && !schema.anyOf.some((branch) => matchesSchema(value, branch, root, depth + 1))) return false;
  if (Array.isArray(schema.enum) && !schema.enum.includes(value)) return false;
  if ("const" in schema && schema.const !== value) return false;
  const type = schema.type;
  if (type === "null") return value === null;
  if (type === "boolean") return typeof value === "boolean";
  if (type === "integer" || type === "number") {
    return typeof value === "number" && Number.isFinite(value) && (type !== "integer" || Number.isInteger(value))
      && (typeof schema.minimum !== "number" || value >= schema.minimum)
      && (typeof schema.maximum !== "number" || value <= schema.maximum);
  }
  if (type === "string") {
    if (typeof value !== "string") return false;
    const length = [...value].length;
    return (typeof schema.minLength !== "number" || length >= schema.minLength)
      && (typeof schema.maxLength !== "number" || length <= schema.maxLength)
      && (typeof schema.pattern !== "string" || new RegExp(schema.pattern, "u").test(value));
  }
  if (type === "array") return Array.isArray(value)
    && (typeof schema.minItems !== "number" || value.length >= schema.minItems)
    && (typeof schema.maxItems !== "number" || value.length <= schema.maxItems)
    && value.every((item) => matchesSchema(item, schema.items, root, depth + 1));
  if (type === "object") {
    if (!value || typeof value !== "object" || Array.isArray(value)) return false;
    const object = value as Schema;
    const properties = (schema.properties ?? {}) as Schema;
    if (Array.isArray(schema.required) && schema.required.some((key) => !Object.hasOwn(object, String(key)))) return false;
    return Object.keys(object).every((key) => Object.hasOwn(properties, key)
      ? matchesSchema(object[key], properties[key], root, depth + 1)
      : schema.additionalProperties !== false);
  }
  return type === undefined && (Array.isArray(schema.anyOf) || Array.isArray(schema.enum) || "const" in schema);
}

/** Read bounded UTF-8 bodies even when Content-Length is absent or dishonest. */
export async function boundedJson(body: ReadableStream<Uint8Array> | null, limit: number): Promise<unknown> {
  if (!body) throw new Error("body_missing");
  const reader = body.getReader();
  const decoder = new TextDecoder("utf-8", { fatal: true });
  let bytes = 0;
  let text = "";
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      bytes += value.byteLength;
      if (bytes > limit) throw new Error("body_too_large");
      text += decoder.decode(value, { stream: true });
    }
    return JSON.parse(text + decoder.decode());
  } finally {
    await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
}
