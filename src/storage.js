const key = "tradex-workspace-v1";

export function loadWorkspace() {
  return JSON.parse(localStorage.getItem(key));
}

export function saveWorkspace(workspace) {
  localStorage.setItem(key, JSON.stringify(workspace));
}
