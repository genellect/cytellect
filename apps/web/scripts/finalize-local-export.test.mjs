import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { finalizeLocalExport } from "./finalize-local-export.mjs";

function fixture(t, { malformed = true, segments = ["_tree", "_full", "plan/__PAGE__"], route = "/plan" } = {}) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "cytellect-flight-"));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const normalized = route === "/" ? "/index" : route;
  const source = path.join(root, `.next/server/app${normalized}.segments`);
  const out = path.join(root, "out");
  const routeDir = path.join(out, route.slice(1));
  fs.mkdirSync(source, { recursive: true });
  fs.mkdirSync(routeDir, { recursive: true });
  const write = (file, bytes) => { fs.mkdirSync(path.dirname(file), { recursive: true }); fs.writeFileSync(file, bytes); };
  const manifest = { version: 4, notFoundRoutes: [], routes: { [route]: { dataRoute: `${normalized}.rsc` } } };
  write(path.join(root, ".next/prerender-manifest.json"), JSON.stringify(manifest));
  for (const segment of segments) {
    const bytes = Buffer.from(`Flight bytes for ${segment}\n`);
    write(path.join(source, `${segment}.segment.rsc`), bytes);
    write(path.join(routeDir, `__next.${malformed ? segment : segment.replaceAll("/", ".")}.txt`), bytes);
  }
  write(path.join(routeDir, "index.html"), "HTML unchanged");
  write(path.join(out, "_next/static/client.js"), "JS unchanged");
  return { root, source, out, routeDir, manifest, write };
}

test("Windows-shaped paths become exact client filenames; repeat and already-flat export are noops", t => {
  const f = fixture(t);
  assert.deepEqual(finalizeLocalExport(f.root), { segments: 3, normalized: 1 });
  assert.equal(fs.readFileSync(path.join(f.routeDir, "__next.plan.__PAGE__.txt"), "utf8"), "Flight bytes for plan/__PAGE__\n");
  assert.equal(fs.existsSync(path.join(f.routeDir, "__next.plan")), false);
  assert.equal(fs.readFileSync(path.join(f.routeDir, "index.html"), "utf8"), "HTML unchanged");
  assert.equal(fs.readFileSync(path.join(f.out, "_next/static/client.js"), "utf8"), "JS unchanged");
  assert.deepEqual(finalizeLocalExport(f.root), { segments: 3, normalized: 0 });
});

for (const route of ["/", "/a/b"]) test(`preserves route hierarchy and encoded/parallel names: ${route}`, t => {
  const f = fixture(t, { route, segments: ["_tree", "a/@modal/!YWJj/__PAGE__"] });
  assert.deepEqual(finalizeLocalExport(f.root), { segments: 2, normalized: 1 });
  assert.equal(fs.readFileSync(path.join(f.routeDir, "__next.a.@modal.!YWJj.__PAGE__.txt"), "utf8"), "Flight bytes for a/@modal/!YWJj/__PAGE__\n");
});

test("Linux-shaped export remains byte-identical", t => {
  const f = fixture(t, { malformed: false });
  assert.deepEqual(finalizeLocalExport(f.root), { segments: 3, normalized: 0 });
});

for (const existing of ["different bytes", "Flight bytes for plan/__PAGE__\n"]) test(`rejects existing destination before moving any files (${existing.length})`, t => {
  const f = fixture(t, { segments: ["a/__PAGE__", "plan/__PAGE__"] });
  f.write(path.join(f.routeDir, "__next.plan.__PAGE__.txt"), existing);
  assert.throws(() => finalizeLocalExport(f.root), /target_collision/);
  assert.equal(fs.existsSync(path.join(f.routeDir, "__next.a.__PAGE__.txt")), false);
  assert.equal(fs.existsSync(path.join(f.routeDir, "__next.a/__PAGE__.txt")), true);
});

test("rejects segment names that collide after encoding", t => {
  const f = fixture(t, { segments: ["a/b", "a.b"] });
  assert.throws(() => finalizeLocalExport(f.root), /target_collision/);
  assert.equal(fs.existsSync(path.join(f.routeDir, "__next.a/b.txt")), true);
});

test("rejects case-insensitive target collisions on every operating system", t => {
  const f = fixture(t, { segments: ["plan/__PAGE__"] });
  f.write(path.join(f.source, "PLAN/__page__.segment.rsc"), "same path with different case");
  assert.throws(() => finalizeLocalExport(f.root), /case_collision|target_collision|segment_bytes/);
  assert.equal(fs.existsSync(path.join(f.routeDir, "__next.plan.__PAGE__.txt")), false);
});

for (const name of ["__next.plan.__PAGE__.txt", "__next.plan/empty"]) test(`rejects destination directory or unknown empty directory (${name}) before writing`, t => {
  const f = fixture(t);
  fs.mkdirSync(path.join(f.routeDir, name), { recursive: true });
  assert.throws(() => finalizeLocalExport(f.root), /target_collision|unrecognized_segment/);
  assert.equal(fs.existsSync(path.join(f.routeDir, "__next.plan/__PAGE__.txt")), true);
});

test("rejects wrong bytes before repairing another valid segment", t => {
  const f = fixture(t, { segments: ["a/__PAGE__", "z/__PAGE__"] });
  f.write(path.join(f.routeDir, "__next.z/__PAGE__.txt"), "wrong response");
  assert.throws(() => finalizeLocalExport(f.root), /segment_bytes/);
  assert.equal(fs.existsSync(path.join(f.routeDir, "__next.a.__PAGE__.txt")), false);
});

test("rejects missing source response and unrecognized exported segments", t => {
  const f = fixture(t);
  fs.unlinkSync(path.join(f.routeDir, "__next._tree.txt"));
  assert.throws(() => finalizeLocalExport(f.root), /segment_missing/);
  f.write(path.join(f.routeDir, "__next._tree.txt"), "Flight bytes for _tree\n");
  f.write(path.join(f.routeDir, "__next.unknown/file.txt"), "unknown");
  assert.throws(() => finalizeLocalExport(f.root), /unrecognized_segment/);
});

for (const target of ["out", ".next/server/app/plan.segments"]) test(`rejects directory symlink/junction (${target}) without outside writes`, t => {
  const f = fixture(t);
  const outside = fs.mkdtempSync(path.join(os.tmpdir(), "cytellect-flight-outside-"));
  t.after(() => fs.rmSync(outside, { recursive: true, force: true }));
  const original = path.join(f.root, target);
  fs.renameSync(original, `${original}-real`);
  fs.symlinkSync(outside, original, process.platform === "win32" ? "junction" : "dir");
  assert.throws(() => finalizeLocalExport(f.root), /linked_path/);
  assert.deepEqual(fs.readdirSync(outside), []);
});

test("rejects a linked descendant before traversal", t => {
  const f = fixture(t);
  fs.symlinkSync(f.source, path.join(f.routeDir, "linked"), process.platform === "win32" ? "junction" : "dir");
  assert.throws(() => finalizeLocalExport(f.root), /linked_path/);
  assert.equal(fs.existsSync(path.join(f.routeDir, "__next.plan.__PAGE__.txt")), false);
});

for (const route of ["/../outside", "/a\\outside", "/C:/outside"]) test(`rejects unsafe manifest route ${route}`, t => {
  const f = fixture(t);
  f.manifest.routes[route] = { dataRoute: "/plan.rsc" };
  f.write(path.join(f.root, ".next/prerender-manifest.json"), JSON.stringify(f.manifest));
  assert.throws(() => finalizeLocalExport(f.root), /invalid_route/);
  assert.equal(fs.existsSync(path.join(f.routeDir, "__next.plan.__PAGE__.txt")), false);
});

test("skips only explicit global-error/not-found routes and static handlers", t => {
  const f = fixture(t);
  f.manifest.routes["/_global-error"] = { dataRoute: "/_global-error.rsc" };
  f.manifest.routes["/missing"] = { dataRoute: "/missing.rsc" };
  f.manifest.routes["/robots.txt"] = {};
  f.manifest.notFoundRoutes.push("/missing");
  f.write(path.join(f.root, ".next/prerender-manifest.json"), JSON.stringify(f.manifest));
  assert.deepEqual(finalizeLocalExport(f.root), { segments: 3, normalized: 1 });
});
