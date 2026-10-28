// Stand-in for app/src/github.js. No sign-in: the world's repo list (real
// public repos, W.repos) answers the installation endpoints, and the relay
// address points at the fake relay that sq/env.mjs serves from node.
import { W } from '../world.mjs';

export const RELAY = 'https://relay.squiggle-ft.invalid/api';
export const apiBase = () => RELAY;
export async function relayConfig() { return { fetchEnabled: false, ai: false }; }
export function resetRelayConfig() {}
export async function loadAuth() { return true; }
export const isSignedIn = () => true;
export async function startDeviceFlow() { throw new Error('No sign-in in node.'); }
export async function pollDeviceFlow() { throw new Error('No sign-in in node.'); }
export async function signOut() {}
export async function gitAuth() { return { username: 'x-access-token', password: '' }; }
export async function relayAi() { const e = new Error('The cloud model is off.'); e.code = 'relay'; throw e; }
export async function relayAiStatus() { return { enabled: false }; }

const USER = { login: 'squiggle-user', id: 1, name: 'Squiggle User' };
const repoInfo = (r) => ({ full_name: r.repo, name: r.repo.split('/')[1], private: false, default_branch: r.default_branch || 'main', description: r.description || '' });

export async function gh(path, { method = 'GET' } = {}) {
  const p = String(path).replace(/^https:\/\/api\.github\.com/, '').split('?')[0];
  if (method === 'GET' && p === '/user') return USER;
  if (method === 'GET' && p === '/user/installations') return { installations: [{ id: 1 }] };
  if (method === 'GET' && p === '/user/installations/1/repositories') return { repositories: W.repos.map(repoInfo) };
  const m = p.match(/^\/repos\/([^/]+)\/([^/]+)$/);
  if (method === 'GET' && m) {
    const r = W.repos.find(x => x.repo.toLowerCase() === `${m[1]}/${m[2]}`.toLowerCase());
    if (r) return repoInfo(r);
  }
  const err = new Error(method === 'GET' ? 'Not Found' : 'Resource not accessible by integration');
  err.status = method === 'GET' ? 404 : 403;
  throw err;
}

export async function getUser() { return USER; }
export async function commitAuthor() { return { name: USER.name, email: `${USER.id}+${USER.login}@users.noreply.github.com` }; }
export async function installations() { return [{ id: 1 }]; }
export async function installationRepos() { return W.repos.map(repoInfo); }
export async function accessibleRepos() { return W.repos.map(repoInfo); }
export async function installUrl() { return 'https://github.com/settings/installations'; }
