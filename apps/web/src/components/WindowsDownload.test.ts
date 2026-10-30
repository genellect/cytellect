import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import WindowsDownload from "./WindowsDownload";

const installer="https://github.com/genellect/cytellect/releases/download/v0.1.0-local.99/Cytellect-Setup-0.1.0-local.99.exe";
const zip="https://github.com/genellect/cytellect/releases/download/v0.1.0-local.99/Cytellect-0.1.0-local.99-windows-x64.zip";
const text=(url:string)=>renderToStaticMarkup(createElement(WindowsDownload,{url})).replace(/<[^>]+>/g," ");

describe("Windows download instructions",()=>{
 it("describe the installer without the ZIP steps",()=>{
  const page=text(installer);
  expect(page).toContain("「インストール」を押します。");
  expect(page).toContain("管理者権限は不要です。");
  expect(page).toContain("メールに届くコードでログイン");
  expect(page).not.toMatch(/ZIP|展開|Cytellect Setup\.cmd|インターネット接続が必要/);
 });
 it("keep the ZIP steps for a version without an installer",()=>{
  const page=text(zip);
  expect(page).toContain("ZIPを展開し、Cytellect Setup.cmdを開きます。");
  expect(page).toContain("初回セットアップにはインターネット接続が必要です。");
  expect(page).not.toContain("「インストール」を押します。");
 });
});
