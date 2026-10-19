const session = new URLSearchParams(location.search).get('setup');
const key = session === null ? 'tradex-workspace-v1' : 'tradex-empty-demo-' + session;
const endpoint = '/api/business/workspace?key=' + encodeURIComponent(session || 'main');
let revision = 0, connected = false, pending = null, saving = false, timer;
let financial = null, business = null;
export const storedBusinessRecords = () => business;
export const storedFinancialState = () => financial;
const report = (status, detail = '') => window.dispatchEvent(new CustomEvent('workspace-storage', {detail:{status,detail}}));

async function request(options) {
  const response = await fetch(endpoint, options);
  const result = await response.json();
  if (!response.ok) throw Error(result.detail || 'Workspace could not be saved.');
  return result;
}

export async function loadWorkspace() {
  const cached = JSON.parse(localStorage.getItem(key));
  try {
    const result = await request();
    revision = result.revision;
    financial = result.financial;
    business = result.business;
    connected = true;
    report('saved');
    return result.workspace || cached;
  } catch (error) {
    report('offline', error.message);
    return cached;
  }
}

export function saveWorkspace(workspace) {
  localStorage.setItem(key, JSON.stringify(workspace));
  if (!connected) return;
  pending = structuredClone(workspace);
  report('saving');
  clearTimeout(timer);
  timer = setTimeout(flushWorkspace, 500);
}

export async function flushWorkspace() {
  if (saving || !pending || !connected) return;
  saving = true;
  const workspace = pending; pending = null;
  try {
    const result = await request({method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({revision,workspace})});
    revision = result.revision;
    financial = result.financial;
    business = result.business;
    window.dispatchEvent(new CustomEvent('workspace-financial', {detail:financial}));
    report(pending ? 'saving' : 'saved');
  } catch (error) {
    connected = false;
    report('error', error.message);
  } finally {
    saving = false;
    if (pending && connected) await flushWorkspace();
  }
}

document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'hidden') flushWorkspace();
});
