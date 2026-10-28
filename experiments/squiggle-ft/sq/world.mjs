// Shared state of one episode's world (one node process runs one episode).
//   files     the storage repo's files (sessions/, memory/, home/…), in memory
//   root      a temp folder that stands in for the browser filesystem (/repos/<name> clones)
//   repoCache folder of pristine clones shared by every episode (filled on first use)
//   netCache  folder of cached web responses shared by every episode
//   repos     GitHub repos the user "gave Squiggle access to" (github_list_repos)
//   generate  async ({ messages, max_tokens, temperature }) => raw model text
export const W = {
  files: new Map(),
  root: null,
  repoCache: null,
  netCache: null,
  offline: false,
  repos: [],
  generate: null,
  approve: 'deny',
  log: [],          // every generation call: { messages, output, kind }
};
