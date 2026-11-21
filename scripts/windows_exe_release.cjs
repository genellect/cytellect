const { execFileSync } = require('node:child_process');
const { createHash } = require('node:crypto');
const { createReadStream, readdirSync, statSync } = require('node:fs');
const { setTimeout: delay } = require('node:timers/promises');

const tagPattern = /^v0\.1\.0-local\.([1-9]\d*)$/;
const shaPattern = /^[a-f0-9]{40}$/;
const requiredJobs = ['python', 'web', 'fiji-browser', 'browser-e2e', 'cellpose-gpu-image',
  'local-windows', 'windows-installed', 'windows-installer', 'python-windows-314'];
const marker = '<!-- cytellect-windows-exe-auto -->';
const channel = 'windows-exe-channel';
const channelFile = 'windows-exe.json';

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
  if (!installer || !manifestAsset || !asset(`${manifestName}.sig`) || !asset(`Cytellect-${version}-gpl-sources.zip`)) {
    throw new Error('The published EXE release is missing required files');
  }
  const response = await fetch(`${base}/${manifestName}`, { signal: AbortSignal.timeout(15_000) });
  if (!response.ok) throw new Error(`The signed manifest is not publicly available (HTTP ${response.status})`);
  const bytes = Buffer.from(await response.arrayBuffer());
  if (`sha256:${createHash('sha256').update(bytes).digest('hex')}` !== manifestAsset.digest) {
    throw new Error('The public update manifest digest differs from the published asset');
  }
  const manifest = JSON.parse(bytes);
  const url = `${base}/${filename}`;
  const download = await fetch(url, { method: 'HEAD', signal: AbortSignal.timeout(15_000) });
  if (!download.ok || installer.browser_download_url !== url ||
      !shaPattern.test(ref.object.sha) || manifest.source_commit !== ref.object.sha ||
      manifest.version !== version || manifest.installer?.name !== filename ||
      manifest.installer.bytes !== installer.size || !/^[a-f0-9]{64}$/.test(manifest.installer.sha256) ||
      installer.digest !== `sha256:${manifest.installer.sha256}`) {
    throw new Error('The public installer differs from the signed update manifest');
  }
  return { version, asset: 'installer', url, sha256: manifest.installer.sha256,
    source_commit: ref.object.sha, size_bytes: installer.size };
}

async function syncChannel(github, context, core) {
  const repo = context.repo;
  const releases = await github.paginate(github.rest.repos.listReleases, { ...repo, per_page: 100 });
  const release = latestPublicRelease(releases);
  if (!release?.body?.includes(marker)) return;
  try {
    await github.rest.git.getRef({ ...repo, ref: `heads/${channel}` });
  } catch (error) {
    if (error.status !== 404) throw error;
    await github.rest.git.createRef({ ...repo, ref: `refs/heads/${channel}`, sha: context.sha });
  }

  const path = { ...repo, path: channelFile };
  let current;
  try {
    ({ data: current } = await github.rest.repos.getContent({ ...path, ref: channel }));
  } catch (error) {
    if (error.status !== 404) throw error;
  }
  if (current) {
    const previous = JSON.parse(Buffer.from(current.content, 'base64').toString('utf8'));
    if (versionNumber(`v${previous.version}`) >= versionNumber(release.tag_name)) return;
  }

  let record;
  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      record = await publicRecord(github, repo, release);
      break;
    } catch (error) {
      if (attempt === 3) throw error;
      await delay(attempt * 10_000);
    }
  }
  await github.rest.repos.createOrUpdateFileContents({
    ...path, branch: channel, sha: current?.sha, message: `Publish Windows EXE ${record.version}`,
    content: Buffer.from(`${JSON.stringify(record, null, 2)}\n`).toString('base64'),
  });
  core.info(`The website channel now points to ${record.version}`);
}

module.exports = { chooseCandidate, mayAttempt, select, reserve, publish, syncChannel };
