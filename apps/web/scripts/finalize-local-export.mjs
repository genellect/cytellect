import fs from "node:fs";
import path from "node:path";

const fail = (reason) => { throw new Error(`local_flight_${reason}`); };
const segmentSuffix = ".segment.rsc";

function checked(root, file) {
  const relative = path.relative(root, file);
  if (relative.startsWith("..") || path.isAbsolute(relative)) fail("outside_root");
  let current = root;
  for (const part of ["", ...relative.split(path.sep).filter(Boolean)]) {
    current = path.join(current, part);
    const stat = fs.lstatSync(current);
    if (stat.isSymbolicLink() || fs.realpathSync(current) !== path.resolve(current)) fail("linked_path");
  }
  return fs.lstatSync(file);
}

function tree(root, directory, directories = []) {
  if (!checked(root, directory).isDirectory()) fail("directory_required");
  directories.push(directory);
  const files = [];
  for (const name of fs.readdirSync(directory).sort()) {
    const file = path.join(directory, name);
    const stat = checked(root, file);
    if (stat.isDirectory()) files.push(...tree(root, file, directories));
    else if (stat.isFile()) files.push(file);
    else fail("regular_file_required");
  }
  return files;
}

function routeParts(value) {
  if (typeof value !== "string" || !value.startsWith("/") || /[\\\0:?#]/.test(value)) fail("invalid_route");
  const parts = value === "/" ? [] : value.slice(1).split("/");
  if (parts.some(part => !part || part === "." || part === "..")) fail("invalid_route");
  return parts;
}

/**
 * Next 16.3.8 collects segment paths with path.relative(), but its export
 * filename encoder replaces only POSIX separators. On Windows this produces
 * directories where the browser requests dotted filenames. Bind every repair
 * to the build's own prerender manifest and original Flight bytes; never infer
 * or manufacture a response from the HTML shell.
 */
export function finalizeLocalExport(webRoot) {
  const root = path.resolve(webRoot);
  const out = path.join(root, "out");
  const manifestFile = path.join(root, ".next/prerender-manifest.json");
  if (!checked(root, manifestFile).isFile()) fail("manifest_required");
  const manifest = JSON.parse(fs.readFileSync(manifestFile, "utf8"));
  if (manifest.version !== 4 || !manifest.routes || !Array.isArray(manifest.notFoundRoutes)) fail("manifest_version");
  const outputDirectories = [];
  const outputFiles = tree(root, out, outputDirectories);
  const actual = new Map();
  for (const file of [...outputFiles, ...outputDirectories]) {
    const key = path.relative(out, file).toLowerCase();
    if (actual.has(key)) fail("case_collision");
    actual.set(key, file);
  }
  const targets = new Set();
  const matched = new Set();
  const moves = [];
  let count = 0;
  for (const [route, metadata] of Object.entries(manifest.routes)) {
    const parts = routeParts(route);
    if (route === "/_global-error" || manifest.notFoundRoutes.includes(route)) continue;
    if (metadata.dataRoute == null) continue; // Static route handlers have no Flight payload.
    if (!metadata.dataRoute.endsWith(".rsc")) fail("data_route_required");
    const sourceParts = routeParts(metadata.dataRoute.slice(0, -4) + ".segments");
    const sourceDir = path.join(root, ".next/server/app", ...sourceParts);
    const routeDir = path.join(out, ...parts);
    checked(root, routeDir);
    for (const source of tree(root, sourceDir)) {
      const relative = path.relative(sourceDir, source).split(path.sep).join("/");
      if (!relative.endsWith(segmentSuffix)) fail("segment_suffix");
      const segment = relative.slice(0, -segmentSuffix.length);
      // Identical to Next's convertSegmentPathToStaticExportFilename after
      // converting the filesystem-relative segment path to POSIX first.
      const target = path.join(routeDir, `__next.${segment.replaceAll("/", ".")}.txt`);
      const malformed = path.join(routeDir, `__next.${segment}.txt`);
      const targetKey = path.relative(out, target).toLowerCase();
      if (targets.has(targetKey)) fail("target_collision");
      targets.add(targetKey);
      const existing = [target, ...(target === malformed ? [] : [malformed])]
        .filter(file => actual.has(path.relative(out, file).toLowerCase()));
      if (existing.length !== 1) fail(existing.length ? "target_collision" : "segment_missing");
      const current = actual.get(path.relative(out, existing[0]).toLowerCase());
      if (current !== existing[0]) fail("case_collision");
      if (!checked(root, current).isFile()) fail("target_collision");
      if (!fs.readFileSync(source).equals(fs.readFileSync(current))) fail("segment_bytes");
      matched.add(current);
      if (current !== target) moves.push({ current, target });
      count++;
    }
  }
  if (!count) fail("segments_required");
  const directories = new Set(moves.flatMap(({ current, target }) => {
    const parents = [];
    for (let directory = path.dirname(current); directory !== path.dirname(target); directory = path.dirname(directory)) parents.push(directory);
    return parents;
  }));
  // Reject unrecognized files AND empty directories before making any changes.
  for (const file of [...outputFiles, ...outputDirectories]) {
    const parts = path.relative(out, file).split(path.sep);
    if (parts.some(part => part.startsWith("__next.")) && !matched.has(file) && !directories.has(file)) fail("unrecognized_segment");
  }
  // All sources, destinations, bytes and collisions are checked before writing.
  for (const { current, target } of moves) {
    checked(root, current);
    checked(root, path.dirname(target));
    fs.writeFileSync(target, fs.readFileSync(current), { flag: "wx" });
    fs.unlinkSync(current);
  }
  for (const directory of [...directories].sort((a, b) => b.length - a.length)) {
    checked(root, directory);
    fs.rmdirSync(directory); // Empty generated segment directories only; never recursive.
  }
  return { segments: count, normalized: moves.length };
}
