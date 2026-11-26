/**
 * Sanitizes a figure SVG produced by the analysis service before it is shown inline.
 *
 * The result is a DOM element, not markup: the caller inserts the node itself, so the
 * sanitized tree is never parsed a second time as HTML. Only SVG-namespace elements on the
 * allow list and their text survive; comments, processing instructions, CDATA sections and
 * any other node type are removed.
 */
const SVG_NAMESPACE = "http://www.w3.org/2000/svg";
const ALLOWED = new Set(["svg", "g", "defs", "path", "rect", "clipPath", "use", "text", "tspan", "line", "circle", "polygon", "polyline", "title", "desc", "metadata", "image"]);
const ELEMENT_NODE = 1;
const TEXT_NODE = 3;

function prune(parent: Node) {
  for (const child of [...parent.childNodes]) {
    if (child.nodeType === ELEMENT_NODE) {
      const element = child as Element;
      if (element.namespaceURI === SVG_NAMESPACE && ALLOWED.has(element.localName) && !element.prefix) prune(element);
      else parent.removeChild(child);
    } else if (child.nodeType !== TEXT_NODE) parent.removeChild(child);
  }
}

/** Returns the sanitized root element with IDs namespaced by `prefix`, or null for anything that is not one SVG figure. */
export function sanitizeFigureSvg(text: string, prefix: string): Element | null {
  const parsed = new DOMParser().parseFromString(text, "image/svg+xml");
  const root = parsed.documentElement;
  if (parsed.querySelector("parsererror") || root.namespaceURI !== SVG_NAMESPACE || root.localName !== "svg" || root.prefix) return null;
  prune(root);
  for (const element of [root, ...root.querySelectorAll("*")]) {
    for (const attribute of [...element.attributes]) {
      // Embedded figure images (representative fields) are inline PNG data, never a fetched URL.
      const inlineImage = element.localName === "image" && /^data:image\/png;base64,/.test(attribute.value);
      if (/^on/i.test(attribute.localName) || /^on/i.test(attribute.name) || (attribute.localName === "href" && !attribute.value.startsWith("#") && !inlineImage) || /url\((?!\s*#)/i.test(attribute.value)) element.removeAttributeNode(attribute);
    }
    if (element.id) { element.setAttribute("data-figure-id", element.id); element.id = prefix + element.id; }
    for (const attribute of [...element.attributes]) {
      if (attribute.localName === "href" && attribute.value.startsWith("#")) element.setAttributeNS(attribute.namespaceURI, attribute.name, "#" + prefix + attribute.value.slice(1));
      else if (attribute.value.includes("url(#")) element.setAttribute(attribute.name, attribute.value.replaceAll("url(#", "url(#" + prefix));
    }
  }
  return root;
}
