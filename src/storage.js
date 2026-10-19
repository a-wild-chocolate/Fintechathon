const session = new URLSearchParams(location.search).get("setup");
const key = session === null ? "tradex-workspace-v1" : "tradex-empty-demo-" + session;

export function loadWorkspace() {
  return JSON.parse(localStorage.getItem(key));
}

export function saveWorkspace(workspace) {
  localStorage.setItem(key, JSON.stringify(workspace));
}
