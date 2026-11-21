const { execFileSync } = require('node:child_process');
const { createHash } = require('node:crypto');
const { createReadStream, mkdtempSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } = require('node:fs');
const { tmpdir } = require('node:os');
const { join } = require('node:path');
const { setTimeout: delay } = require('node:timers/promises');

const tagPattern = /^v0\.1\.0-local\.([1-9]\d*)$/;
const shaPattern = /^[a-f0-9]{40}$/;
const requiredJobs = ['python', 'web', 'fiji-browser', 'browser-e2e', 'cellpose-gpu-image',
  'local-windows', 'windows-installed', 'windows-installer', 'python-windows-314'];
const marker = '<!-- cytellect-windows-exe-auto -->';
const channel = 'windows-exe-channel';
const channelFile = 'windows-exe.json';
const signingKeyFile = 'services/api/src/cytellect_api/update_signature.py';

function versionNumber(tag) {
  return Number(tagPattern.exec(tag)?.[1] ?? 0);
}

function chooseCandidate(history, successful, publishedCommit) {
  const latest = history.find(sha => successful.has(sha));
  if (!latest) return '';
  if (!publishedCommit) return latest;
  const publishedIndex = history.indexOf(publishedCommit);
  if (publishedIndex < 0) throw new Error('The published EXE tag is outside main history');
  return history.indexOf(latest) < publishedIndex ? latest : '';
}

// A scheduled run resumes a reserved candidate only from its tested package. Building it again
// waits for a new commit or for the owner's `automatic` dispatch, so a failing build is not repeated.
function mayAttempt(eventName, reserved, packaged) {
  return eventName !== 'schedule' || !reserved || packaged;
}

function latestPublicRelease(releases) {
  return releases.filter(release => !release.draft && versionNumber(release.tag_name)
    && release.assets.some(asset => asset.name === `Cytellect-Setup-${release.tag_name.slice(1)}.exe`))
    .sort((a, b) => versionNumber(b.tag_name) - versionNumber(a.tag_name))[0];
}

async function select(github, context, core) {
  const repo = context.repo;
  const releases = await github.paginate(github.rest.repos.listReleases, { ...repo, per_page: 100 });
  const published = latestPublicRelease(releases);
  const tags = await github.paginate(github.rest.repos.listTags, { ...repo, per_page: 100 });
  const releaseTags = tags.filter(tag => versionNumber(tag.name));
  const publishedCommit = published && releaseTags.find(tag => tag.name === published.tag_name)?.commit.sha;
  if (published && !publishedCommit) throw new Error('The published EXE does not have a source tag');

  const history = execFileSync('git', ['rev-list', '--first-parent', 'origin/main'], { encoding: 'utf8' }).trim().split('\n');
  const runs = await github.paginate(github.rest.actions.listWorkflowRuns, {
    ...repo, workflow_id: 'ci.yml', branch: 'main', event: 'push', status: 'success', per_page: 100,
  });
  const verified = new Set();
  for (const run of runs) {
    if (run.head_repository?.id === context.payload.repository.id) verified.add(run.head_sha);
  }
  const commit = chooseCandidate(history, verified, publishedCommit);
  if (!commit) return;
  const run = runs.find(item => item.head_sha === commit && item.head_repository?.id === context.payload.repository.id);
  const jobs = await github.paginate(github.rest.actions.listJobsForWorkflowRun, {
    ...repo, run_id: run.id, filter: 'latest', per_page: 100,
  });
  for (const name of requiredJobs) {
    if (!jobs.some(job => job.name === name && job.conclusion === 'success')) {
      throw new Error(`${name} has not passed on ${commit}`);
    }
  }

  const candidates = releaseTags.filter(tag => {
    const release = releases.find(item => item.tag_name === tag.name);
    return tag.commit.sha === commit && versionNumber(tag.name) > versionNumber(published?.tag_name)
      && (!release || (release.draft && release.body?.includes(marker)));
  });
  if (candidates.length > 1) throw new Error('The selected commit has multiple unpublished EXE versions');
  const next = Math.max(0, ...releases.map(release => versionNumber(release.tag_name)),
    ...releaseTags.map(tag => versionNumber(tag.name))) + 1;
  if (!Number.isSafeInteger(next)) throw new Error('The EXE version number is out of range');
  const version = candidates[0]?.name.slice(1) ?? `0.1.0-local.${next}`;
  let artifactRun = '';
  const name = `auto-exe-${version}-${commit}`;
  const artifacts = await github.paginate(github.rest.actions.listArtifactsForRepo, { ...repo, name, per_page: 100 });
  for (const artifact of artifacts) {
    if (artifact.expired || artifact.workflow_run?.head_branch !== 'main' ||
        artifact.workflow_run?.head_repository_id !== context.payload.repository.id) continue;
    const run_id = artifact.workflow_run.id;
    const { data: prior } = await github.rest.actions.getWorkflowRun({ ...repo, run_id });
    if (prior.path !== '.github/workflows/local-release.yml' ||
        !['workflow_run', 'workflow_dispatch', 'schedule'].includes(prior.event)) continue;
    const { data: priorJobs } = await github.rest.actions.listJobsForWorkflowRun({
      ...repo, run_id, filter: 'latest', per_page: 100,
    });
    if (priorJobs.jobs.some(job => job.name === 'package' && job.conclusion === 'success')) {
      artifactRun = String(run_id);
      break;
    }
  }
  if (!mayAttempt(context.eventName, candidates.length === 1, artifactRun !== '')) {
    core.info(`${version} is reserved for ${commit} without a tested package; a scheduled run does not rebuild it`);
    return;
  }
  core.setOutput('commit', commit);
  core.setOutput('version', version);
  core.setOutput('artifact-run', artifactRun);
  core.info(`Selected ${commit} in Verify run ${run.id} for ${version}`);
}

async function reserve(github, context) {
  const sha = process.env.RELEASE_COMMIT;
  const tag = `v${process.env.RELEASE_VERSION}`;
  if (!shaPattern.test(sha) || !versionNumber(tag)) throw new Error('Invalid EXE version reservation');
  const ref = `tags/${tag}`;
  try {
    await github.rest.git.createRef({ ...context.repo, ref: `refs/${ref}`, sha });
  } catch (error) {
    if (error.status !== 422) throw error;
    const { data } = await github.rest.git.getRef({ ...context.repo, ref });
    if (data.object.type !== 'commit' || data.object.sha !== sha) throw error;
  }
}

async function verifyAttached(release, directory) {
  for (const file of readdirSync(directory)) {
    const path = `${directory}/${file}`;
    const hash = createHash('sha256');
    for await (const chunk of createReadStream(path)) hash.update(chunk);
    const asset = release.assets.find(item => item.name === file);
    if (asset?.state !== 'uploaded' || asset.size !== statSync(path).size || asset.digest !== `sha256:${hash.digest('hex')}`) {
      throw new Error(`The draft asset ${file} does not match the tested release`);
    }
  }
}

async function publish(github, context, core, directory = 'release') {
  const repo = context.repo;
  const commit = process.env.RELEASE_COMMIT;
  const tag = `v${process.env.RELEASE_VERSION}`;
  if (!shaPattern.test(commit) || !versionNumber(tag)) throw new Error('Invalid EXE release identity');
  const { data: ref } = await github.rest.git.getRef({ ...repo, ref: `tags/${tag}` });
  if (ref.object.sha !== commit) throw new Error('The release tag does not identify the tested commit');
  const releases = await github.paginate(github.rest.repos.listReleases, { ...repo, per_page: 100 });
  const draft = releases.find(release => release.tag_name === tag);
  if (!draft?.body?.includes(marker) || !draft.prerelease) throw new Error('Expected an automatic EXE prerelease');
  if (!draft.draft) return;
  const previous = latestPublicRelease(releases);
  if (previous) {
    const { data: comparison } = await github.rest.repos.compareCommitsWithBasehead({
      ...repo, basehead: `${previous.tag_name}...${commit}`, per_page: 1,
    });
    if (comparison.status !== 'ahead' || versionNumber(previous.tag_name) >= versionNumber(tag)) {
      throw new Error('The EXE candidate is older than, or equal to, the published release');
    }
  }
  await verifyAttached(draft, directory);
  await github.rest.repos.updateRelease({ ...repo, release_id: draft.id, draft: false });
  core.info(`Published ${tag} from ${commit}`);
}

async function publicRecord(github, repo, release) {
  const tag = release.tag_name;
  const version = tag.slice(1);
  const { data: ref } = await github.rest.git.getRef({ ...repo, ref: `tags/${tag}` });
  const base = `https://github.com/${repo.owner}/${repo.repo}/releases/download/${tag}`;
  const filename = `Cytellect-Setup-${version}.exe`;
  const manifestName = `Cytellect-update-${version}.json`;
  const asset = name => release.assets.find(item => item.name === name && item.state === 'uploaded');
  const installer = asset(filename);
  const manifestAsset = asset(manifestName);
  const signatureAsset = asset(`${manifestName}.sig`);
  if (!installer || !manifestAsset || !signatureAsset || !asset(`Cytellect-${version}-gpl-sources.zip`)) {
    throw new Error('The published EXE release is missing required files');
  }
  const response = await fetch(`${base}/${manifestName}`, { signal: AbortSignal.timeout(15_000) });
  const signatureResponse = await fetch(`${base}/${signatureAsset.name}`, { signal: AbortSignal.timeout(15_000) });
  if (!response.ok || !signatureResponse.ok) throw new Error('The manifest and signature must both be publicly available');
  const bytes = Buffer.from(await response.arrayBuffer());
  const signature = Buffer.from(await signatureResponse.arrayBuffer());
  if (`sha256:${createHash('sha256').update(bytes).digest('hex')}` !== manifestAsset.digest) {
    throw new Error('The public update manifest digest differs from the published asset');
  }
  const manifest = JSON.parse(bytes);
  const url = `${base}/${filename}`;
  const download = await fetch(url, { method: 'HEAD', signal: AbortSignal.timeout(15_000) });
  if (!download.ok || installer.browser_download_url !== url ||
      !shaPattern.test(ref.object.sha) || manifest.source_commit !== ref.object.sha ||
      manifest.schema !== 'cytellect-update-manifest/1' || manifest.version !== version || manifest.installer?.name !== filename ||
      manifest.installer.bytes !== installer.size || !/^[a-f0-9]{64}$/.test(manifest.installer.sha256) ||
      installer.digest !== `sha256:${manifest.installer.sha256}`) {
    throw new Error('The public installer differs from the signed update manifest');
  }
  return {
    record: { version, asset: 'installer', url, sha256: manifest.installer.sha256,
      source_commit: ref.object.sha, size_bytes: installer.size },
    manifest: bytes,
    signature,
  };
}

function verifyChannelSignature(manifest, signature, previousSource) {
  const source = readFileSync(signingKeyFile, 'utf8');
  const key = /^UPDATE_PUBLIC_KEY = "(ssh-ed25519 [A-Za-z0-9+/=]+)(?: [^"\r\n]*)?"\r?$/m;
  const signers = new Set([key.exec(source)?.[1], key.exec(previousSource)?.[1]].filter(Boolean));
  if (!signers.size || manifest.length > 64 * 1024 || signature.length > 16 * 1024) {
    throw new Error('The public update manifest or trusted signing key is invalid');
  }
  const directory = mkdtempSync(join(tmpdir(), 'cytellect-channel-'));
  try {
    const allowed = join(directory, 'allowed_signers');
    const detached = join(directory, 'manifest.sig');
    writeFileSync(allowed, Array.from(signers, signer => `cytellect-update ${signer}\n`).join(''));
    writeFileSync(detached, signature);
    execFileSync('ssh-keygen', ['-Y', 'verify', '-f', allowed, '-I', 'cytellect-update', '-n', 'cytellect-update', '-s', detached],
      { input: manifest, stdio: ['pipe', 'ignore', 'ignore'] });
  } catch {
    throw new Error('The public update manifest signature is not trusted');
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
}

function pushChannel(record, expectedHead) {
  const git = (...args) => execFileSync('git', args, { encoding: 'utf8' }).trim();
  const ref = `refs/heads/${channel}`;
  if (expectedHead) {
    git('fetch', '--no-tags', 'origin', ref);
    if (git('rev-parse', 'FETCH_HEAD') !== expectedHead) throw new Error('The website channel advanced during verification');
    git('switch', '--detach', expectedHead);
  }
  writeFileSync(channelFile, `${JSON.stringify(record, null, 2)}\n`);
  git('add', '--sparse', '--', channelFile);
  git('-c', 'user.name=Cytellect EXE release', '-c', 'user.email=github-actions[bot]@users.noreply.github.com',
    'commit', '-m', `Publish Windows EXE ${record.version}`);
  git('push', 'origin', `HEAD:${ref}`);
}

async function syncChannel(github, context, core, {
  writeRecord = pushChannel, seedFromPublished = false, verifySignature = verifyChannelSignature,
} = {}) {
  const repo = context.repo;
  const releases = await github.paginate(github.rest.repos.listReleases, { ...repo, per_page: 100 });
  const release = latestPublicRelease(releases);
  if (!release || (!seedFromPublished && !release.body?.includes(marker))) return;
  let head;
  let previous;
  try {
    const { data: ref } = await github.rest.git.getRef({ ...repo, ref: `heads/${channel}` });
    head = ref.object.sha;
  } catch (error) {
    if (error.status !== 404) throw error;
  }
  if (head) {
    try {
      const { data: current } = await github.rest.repos.getContent({ ...repo, path: channelFile, ref: head });
      previous = JSON.parse(Buffer.from(current.content, 'base64').toString('utf8'));
      if (versionNumber(`v${previous.version}`) >= versionNumber(release.tag_name)) return;
    } catch (error) {
      if (error.status !== 404) throw error;
    }
  }

  let candidate;
  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      candidate = await publicRecord(github, repo, release);
      break;
    } catch (error) {
      if (attempt === 3) throw error;
      await delay(attempt * 10_000);
    }
  }
  // A rotation can be signed by the key in the previous verified record. Release tags and
  // assets do not select trusted keys.
  let previousSource = '';
  if (shaPattern.test(previous?.source_commit)) {
    const { data: source } = await github.rest.repos.getContent({
      ...repo, path: signingKeyFile, ref: previous.source_commit,
    });
    previousSource = Buffer.from(source.content, 'base64').toString('utf8');
  }
  const { record, manifest, signature } = candidate;
  verifySignature(manifest, signature, previousSource);
  await writeRecord(record, head);
  core.info(`The website channel now points to ${record.version}`);
}

module.exports = { chooseCandidate, mayAttempt, select, reserve, publish, syncChannel };
