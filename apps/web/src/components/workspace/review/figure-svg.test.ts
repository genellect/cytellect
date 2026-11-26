// @vitest-environment jsdom
import {describe,expect,it} from "vitest";
import {sanitizeFigureSvg} from "./figure-svg";

const NS='xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"';
const wrap=(body:string,before="")=>`<?xml version="1.0"?>${before}<svg ${NS} viewBox="0 0 10 10">${body}</svg>`;
function nodeTypes(root:Node){const seen=new Set<number>();const walk=(node:Node)=>{for(const child of node.childNodes){seen.add(child.nodeType);walk(child);}};walk(root);return seen;}
/** What an HTML parser would build from the serialized result: the check that a re-parse stays inert. */
function asHtml(root:Element){const holder=document.createElement("div");holder.innerHTML=new XMLSerializer().serializeToString(root);return holder;}

describe("sanitizeFigureSvg",()=>{
  it("keeps only elements and text: no processing instruction, comment or CDATA survives",()=>{
    const root=sanitizeFigureSvg(wrap('<?pi <img src="x" onerror="1"/> ?><!-- <script>1</script> --><g id="a"><![CDATA[<script>1</script>]]><text>label</text><?inner <iframe/> ?></g>'),"p-");
    expect(root).not.toBeNull();
    expect([...nodeTypes(root!)].sort()).toEqual([1,3]);
    expect(root!.textContent).toBe("label");
    const html=asHtml(root!);
    expect(html.querySelector("script,img,iframe")).toBeNull();
    expect(nodeTypes(html).has(8)).toBe(false);
  });
  it("removes elements off the allow list, including allowed names in another namespace",()=>{
    const root=sanitizeFigureSvg(wrap('<script>1</script><style>*{}</style><foreignObject><p xmlns="http://www.w3.org/1999/xhtml">x</p></foreignObject><animate/><set/><image xmlns="http://www.w3.org/1999/xhtml" src="x"/><g><a href="#x"><rect/></a><path d="M0 0"/></g>'),"p-")!;
    expect([...root.querySelectorAll("*")].map(element=>element.localName)).toEqual(["g","path"]);
  });
  it("removes event handlers and every external reference, and keeps inline PNG images",()=>{
    const root=sanitizeFigureSvg(wrap('<rect onclick="1" ONLOAD="1" fill="url(https://example.invalid/a)" style="fill:url( //example.invalid/b)"/><use xlink:href="https://example.invalid/c#d"/><use href="javascript:1"/><image href="data:image/svg+xml;base64,AAAA"/><image id="keep" href="data:image/png;base64,AAAA"/>'),"p-")!;
    const attributes=[...root.querySelectorAll("*")].flatMap(element=>[...element.attributes].map(attribute=>`${element.localName}.${attribute.name}`));
    expect(attributes.sort()).toEqual(["image.data-figure-id","image.href","image.id"]);
    expect(root.querySelector("image[id]")!.getAttribute("href")).toBe("data:image/png;base64,AAAA");
  });
  it("namespaces IDs and their internal references",()=>{
    const root=sanitizeFigureSvg(wrap('<defs><clipPath id="c"><rect/></clipPath><path id="m" d="M0 0"/></defs><g clip-path="url(#c)"><use xlink:href="#m"/></g>'),"p-")!;
    expect(root.querySelector("clipPath")!.id).toBe("p-c");
    expect(root.querySelector("clipPath")!.getAttribute("data-figure-id")).toBe("c");
    expect(root.querySelector("g")!.getAttribute("clip-path")).toBe("url(#p-c)");
    expect(root.querySelector("use")!.getAttributeNS("http://www.w3.org/1999/xlink","href")).toBe("#p-m");
  });
  it("rejects input that is not one well-formed SVG document",()=>{
    expect(sanitizeFigureSvg("<svg><g></svg>","p-")).toBeNull();
    expect(sanitizeFigureSvg('<html xmlns="http://www.w3.org/1999/xhtml"><body/></html>',"p-")).toBeNull();
    expect(sanitizeFigureSvg("<svg/>","p-")).toBeNull();
  });
});
