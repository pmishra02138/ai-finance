#!/usr/bin/env node
/**
 * Unified Node.js frontend server for AI Personal Finance Advisor.
 *
 * - Serves static SPA assets from ./public on PORT (default: 3000)
 * - Reverse-proxies /api/* requests to the FastAPI backend (BACKEND_URL, default: http://127.0.0.1:8787)
 */

const http = require("node:http");
const https = require("node:https");
const fs = require("node:fs");
const path = require("node:path");
const { URL } = require("node:url");

const HOST = process.env.HOST || "127.0.0.1";
const PORT = Number(process.env.PORT || 3000);
const BACKEND_URL = (process.env.BACKEND_URL || "http://127.0.0.1:8787").replace(/\/+$/, "");
const PUBLIC_DIR = path.join(__dirname, "public");

const MIME_TYPES = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".ico": "image/x-icon",
};

function proxyToBackend(req, res) {
  const strippedPath = req.url.replace(/^\/api/, "") || "/";
  const target = new URL(strippedPath, BACKEND_URL + "/");
  const client = target.protocol === "https:" ? https : http;

  const headers = { ...req.headers, host: target.host };
  const proxyReq = client.request(
    {
      hostname: target.hostname,
      port: target.port || (target.protocol === "https:" ? 443 : 80),
      path: target.pathname + target.search,
      method: req.method,
      headers,
    },
    (proxyRes) => {
      res.writeHead(proxyRes.statusCode || 502, proxyRes.headers);
      proxyRes.pipe(res);
    }
  );

  proxyReq.on("error", (err) => {
    res.writeHead(502, { "Content-Type": "application/json; charset=utf-8" });
    res.end(
      JSON.stringify({
        detail: "Backend API unreachable",
        backend: BACKEND_URL,
        error: err.message,
      })
    );
  });

  req.pipe(proxyReq);
}

function serveStatic(req, res) {
  const urlObj = new URL(req.url, `http://${HOST}:${PORT}`);
  let relPath = decodeURIComponent(urlObj.pathname);
  if (relPath === "/") relPath = "/index.html";

  const fullPath = path.normalize(path.join(PUBLIC_DIR, relPath));
  if (!fullPath.startsWith(PUBLIC_DIR)) {
    res.writeHead(403, { "Content-Type": "text/plain" });
    res.end("Forbidden");
    return;
  }

  fs.stat(fullPath, (err, stats) => {
    if (err || !stats.isFile()) {
      const fallback = path.join(PUBLIC_DIR, "index.html");
      fs.readFile(fallback, (fbErr, data) => {
        if (fbErr) {
          res.writeHead(404, { "Content-Type": "text/plain" });
          res.end("Not Found");
          return;
        }
        res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
        res.end(data);
      });
      return;
    }

    const ext = path.extname(fullPath).toLowerCase();
    res.writeHead(200, { "Content-Type": MIME_TYPES[ext] || "application/octet-stream" });
    fs.createReadStream(fullPath).pipe(res);
  });
}

const server = http.createServer((req, res) => {
  if (req.url === "/api" || req.url.startsWith("/api/")) {
    proxyToBackend(req, res);
    return;
  }
  serveStatic(req, res);
});

server.on("error", (err) => {
  if (err.code === "EADDRINUSE") {
    console.error(`Error: Port ${PORT} on ${HOST} is already in use. Stop the existing process or pass PORT=3001.`);
  } else {
    console.error(`Server error: ${err.message}`);
  }
  process.exit(1);
});

server.listen(PORT, HOST, () => {
  console.log(`ai-finance Node.js frontend listening on http://${HOST}:${PORT} (API proxy -> ${BACKEND_URL})`);
});
