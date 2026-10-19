const params = new URLSearchParams(location.search);
if (params.has('demo') || params.has('setup')) {
  const response = await fetch('/api/agents/workspace');
  if (!response.ok) {
    document.getElementById('tradeflow-export-preview').textContent = 'Start the backend to open the workspace.';
  } else {
    const {workspace} = await response.json();
    if (workspace.kind === 'business') {
      location.replace('/?company=' + encodeURIComponent(workspace.company_id) + '&lang=' + (params.get('lang') || 'en'));
    } else {
      const content = document.getElementById('legacy-workspace').content.cloneNode(true);
      document.getElementById('tradeflow-export-preview').replaceChildren(content);
      await import('./app.js');
    }
  }
} else await import('./business-ui.js');
