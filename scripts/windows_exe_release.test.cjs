const assert = require('node:assert/strict');
const { createHash } = require('node:crypto');
const { mkdtempSync, rmdirSync, unlinkSync, writeFileSync } = require('node:fs');
const { tmpdir } = require('node:os');
const { join } = require('node:path');
const { test } = require('node:test');
const { chooseCandidate, mayAttempt, reserve, publish, syncChannel } = require('./windows_exe_release.cjs');

test('selects by main history and never regresses to a release that completed late', () => {
  const history = ['newest', 'middle', 'published', 'oldest'];
  assert.equal(chooseCandidate(history, new Set(['oldest', 'middle', 'newest']), 'published'), 'newest');
  assert.equal(chooseCandidate(history, new Set(['middle']), 'published'), 'middle');
  assert.equal(chooseCandidate(history, new Set(['oldest']), 'published'), '');
  assert.equal(chooseCandidate(history, new Set(['published']), 'published'), '');
  assert.throws(() => chooseCandidate(history, new Set(['middle']), 'off-main'));
});

test('a scheduled run does not rebuild a reserved candidate that has no tested package', () => {
  assert.equal(mayAttempt('schedule', true, false), false);
  assert.equal(mayAttempt('schedule', true, true), true);
  assert.equal(mayAttempt('schedule', false, false), true);
  assert.equal(mayAttempt('workflow_run', true, false), true);
  assert.equal(mayAttempt('workflow_dispatch', true, false), true);
});

const commit = 'a'.repeat(40);
const version = '0.1.0-local.25';

function candidateEnvironment(t) {
  const values = { RELEASE_COMMIT: commit, RELEASE_VERSION: version };
  const previous = Object.keys(values).map(key => [key, process.env[key]]);
  Object.assign(process.env, values);
  t.after(() => {
    for (const [key, value] of previous) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
  });
}

test('resumes a reserved tag only if it still identifies the candidate commit', async t => {
  candidateEnvironment(t);
  const collision = Object.assign(new Error('already exists'), { status: 422 });
  const ref = { object: { sha: commit, type: 'commit' } };
  const github = { rest: { git: {
    createRef: async () => { throw collision; },
    getRef: async () => ({ data: ref }),
  } } };
  await reserve(github, { repo: {} });
  ref.object.sha = 'b'.repeat(40);
  await assert.rejects(reserve(github, { repo: {} }), collision);
});

test('preserves the current public release unless draft assets match the tested files', async t => {
  candidateEnvironment(t);
  const directory = mkdtempSync(join(tmpdir(), 'cytellect-release-test-'));
  const name = `Cytellect-Setup-${version}.exe`;
  const bytes = Buffer.from('tested installer');
  const installer = join(directory, name);
  writeFileSync(installer, bytes);
  t.after(() => {
    unlinkSync(installer);
    rmdirSync(directory);
  });
  const asset = { name, state: 'uploaded', size: bytes.length, digest: 'sha256:wrong' };
  const draft = { id: 10, tag_name: `v${version}`, draft: true, prerelease: true,
    body: '<!-- cytellect-windows-exe-auto -->', assets: [asset] };
  const previous = { tag_name: 'v0.1.0-local.24', draft: false, assets: [{ name: 'Cytellect-Setup-0.1.0-local.24.exe' }] };
  let ordering = 'ahead';
  let published = 0;
  const github = {
    paginate: async () => [draft, previous],
    rest: {
      git: { getRef: async () => ({ data: { object: { sha: commit } } }) },
      repos: {
        compareCommitsWithBasehead: async () => ({ data: { status: ordering } }),
        updateRelease: async ({ release_id, draft: isDraft }) => {
          assert.equal(release_id, draft.id);
          assert.equal(isDraft, false);
          draft.draft = false;
          published++;
        },
      },
    },
  };
  const run = () => publish(github, { repo: {} }, { info() {} }, directory);
  await assert.rejects(run(), /does not match/);
  asset.digest = `sha256:${createHash('sha256').update(bytes).digest('hex')}`;
  ordering = 'behind';
  await assert.rejects(run(), /older than/);
  assert.equal(published, 0);
  ordering = 'ahead';
  await run();
  await run();
  assert.equal(published, 1);
});

test('repairs the website record from the same published installer after a failed write', async t => {
  const installer = { name: `Cytellect-Setup-${version}.exe`, sha256: 'b'.repeat(64), bytes: 123 };
  const base = `https://github.com/genellect/cytellect/releases/download/v${version}`;
  const manifest = JSON.stringify({ version, source_commit: commit, installer });
  const manifestName = `Cytellect-update-${version}.json`;
  const upload = name => ({ name, state: 'uploaded' });
  const release = { tag_name: `v${version}`, draft: false, body: 'Manually published', assets: [
    { ...upload(installer.name), size: installer.bytes, digest: `sha256:${installer.sha256}`, browser_download_url: `${base}/${installer.name}` },
    { ...upload(manifestName), digest: `sha256:${createHash('sha256').update(manifest).digest('hex')}` },
    upload(`${manifestName}.sig`),
    upload(`Cytellect-${version}-gpl-sources.zip`),
  ] };
  t.mock.method(globalThis, 'fetch', async (url, request) => {
    if (url === `${base}/${manifestName}`) return new Response(manifest);
    assert.equal(url, `${base}/${installer.name}`);
    assert.equal(request.method, 'HEAD');
    return new Response();
  });
  let content;
  let writes = 0;
  const github = {
    paginate: async () => [release],
    rest: {
      git: { getRef: async () => ({ data: { object: { sha: commit } } }) },
      repos: {
        getContent: async () => {
          if (!content) throw Object.assign(new Error('not found'), { status: 404 });
          return { data: { content, sha: 'file-sha' } };
        },
      },
    },
  };
  const context = { repo: { owner: 'genellect', repo: 'cytellect' } };
  const core = { info() {} };
  const write = async (record, head) => {
    if (++writes === 1) throw new Error('write failed');
    assert.equal(head, commit);
    content = Buffer.from(JSON.stringify(record)).toString('base64');
  };
  await syncChannel(github, context, core, { writeRecord: write });
  assert.equal(writes, 0);
  await assert.rejects(syncChannel(github, context, core, { writeRecord: write, seedFromPublished: true }), /write failed/);
  await syncChannel(github, context, core, { writeRecord: write, seedFromPublished: true });
  await syncChannel(github, context, core, { writeRecord: write, seedFromPublished: true });
  assert.equal(writes, 2);
  assert.deepEqual(JSON.parse(Buffer.from(content, 'base64')), {
    version, asset: 'installer', url: `${base}/${installer.name}`, sha256: installer.sha256,
    source_commit: commit, size_bytes: installer.bytes,
  });
});
