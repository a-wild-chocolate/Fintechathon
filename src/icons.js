const paths = {
  bell: '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/>',
  "layout-dashboard":
    '<rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/>',
  sparkles:
    '<path d="m12 3 2.6 6.4L21 12l-6.4 2.6L12 21l-2.6-6.4L3 12l6.4-2.6Z"/>',
  package: '<path d="m12 3 9 5v9l-9 5-9-5V8Zm-9 5 9 5 9-5M12 13v9M7 5.8l9 5"/>',
  files: '<path d="M8 3h8l4 4v13H8ZM16 3v5h4M4 7v16h12"/>',
  "folder-open": '<path d="M3 7V4h6l3 3h9v13H3ZM3 10h18l-3 10H3Z"/>',
  "chart-no-axes-combined":
    '<path d="M4 20V10m6 10V5m6 15v-8m5 8V3M3 8l7-5 6 5 5-6"/>',
  "list-checks":
    '<path d="m3 6 2 2 4-4m-6 9 2 2 4-4m-6 9 2 2 4-4M13 6h8m-8 7h8m-8 7h8"/>',
};

export function renderIcons(root) {
  for (const icon of root.querySelectorAll("[data-lucide]")) {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("width", "16");
    svg.setAttribute("height", "16");
    svg.setAttribute("fill", "none");
    svg.setAttribute("stroke", "currentColor");
    svg.setAttribute("stroke-width", "1.6");
    svg.setAttribute("stroke-linecap", "round");
    svg.setAttribute("stroke-linejoin", "round");
    svg.setAttribute("aria-hidden", "true");
    svg.innerHTML = paths[icon.dataset.lucide];
    icon.replaceWith(svg);
  }
}
