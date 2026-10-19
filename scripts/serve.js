import { createServer, request as upstreamRequest } from "node:http";
import { readFile } from "node:fs/promises";
import { resolve, extname, sep } from "node:path";

const root = resolve(process.argv[2] || ".");
const port = Number(process.env.PORT || 5173);
const mime = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".txt": "text/plain; charset=utf-8",
  ".csv": "text/csv; charset=utf-8",
  ".svg": "image/svg+xml",
};

createServer(async (request, response) => {
  const pathname = new URL(request.url, "http://localhost").pathname;
  if (pathname === "/" && process.env.TRADEX_DEMO_SESSION && new URL(request.url, "http://localhost").searchParams.get("setup") !== process.env.TRADEX_DEMO_SESSION) {
    response.writeHead(302, { Location: "/?setup=" + encodeURIComponent(process.env.TRADEX_DEMO_SESSION) }).end();
    return;
  }
  if (pathname.startsWith('/api/') || pathname === '/knowledge') {
    const upstream = upstreamRequest({
      hostname: '127.0.0.1', port: Number(process.env.TRADEX_RAG_PORT || 8765),
      path: pathname === '/knowledge' ? '/' : request.url,
      method: request.method, headers: { ...request.headers, host: '127.0.0.1:8765' },
    }, result => {
      response.writeHead(result.statusCode, result.headers);
      result.pipe(response);
    });
    upstream.on('error', () => {
      if (!response.headersSent) response.writeHead(503, { 'Content-Type': 'application/json' });
      response.end(JSON.stringify({ detail: 'Knowledge service is offline. Start tradex-rag/start.sh.' }));
    });
    request.pipe(upstream);
    return;
  }
  const file = resolve(
    root,
    "." + (pathname === "/" ? "/index.html" : pathname),
  );
  if (!file.startsWith(root + sep) || !mime[extname(file)]) {
    response.writeHead(404).end("Not found");
    return;
  }
  try {
    const content = await readFile(file);
    response.writeHead(200, {
      "Content-Type": mime[extname(file)],
      "Cache-Control": "no-store",
    });
    response.end(content);
  } catch (error) {
    response.writeHead(error.code === "ENOENT" ? 404 : 500).end(error.code);
  }
}).listen(port, "127.0.0.1", () => {
  console.log(`TradeX ready: http://127.0.0.1:${port}`);
});
