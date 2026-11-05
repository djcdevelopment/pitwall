import { defineConfig, type Plugin } from "vite";
import fs from "node:fs";
import path from "node:path";

// Dev-only: serve web/dev sample data when PITWALL_DEV_SAMPLE=1. Never part of the build.
function devSample(): Plugin {
  const dir = path.resolve(__dirname, "dev");
  const read = (f: string) => fs.readFileSync(path.join(dir, f), "utf8");
  return {
    name: "pitwall-dev-sample",
    apply: "serve",
    configureServer(server) {
      if (process.env.PITWALL_DEV_SAMPLE !== "1") return;
      server.middlewares.use((req, res, next) => {
        const url = new URL(req.url ?? "/", "http://x");
        const p = url.pathname;
        if (!p.startsWith("/api/")) return next();
        const send = (body: string, type = "application/json") => {
          res.setHeader("content-type", type);
          res.end(body);
        };
        try {
          const mode = url.searchParams.get("mode") ?? "live";
          if (p === "/api/snapshot") {
            const f = mode === "demo" ? "sample-demo.json" : "sample-snapshot.json";
            const body = read(f);
            const etag = `"s${body.length}"`;
            res.setHeader("etag", etag);
            if (req.headers["if-none-match"] === etag) { res.statusCode = 304; return res.end(); }
            return send(body);
          }
          if (p === "/api/history") return send(read("sample-history.json"));
          if (p === "/api/scenarios") return send(JSON.stringify([
            { id: "idle", note: "synthetic pairing: idle fleet, completed task" },
            { id: "active", note: "synthetic pairing: serving fleet, live task" },
            { id: "degraded", note: "synthetic pairing: unreachable host" },
            { id: "recovered", note: "synthetic pairing: recovered delivery" },
          ]));
          if (p === "/api/evidence/relpack") return send(read("sample-evidence-index.json"));
          if (p.startsWith("/api/evidence/relpack/")) {
            const rec = p.split("/").pop();
            if (rec === "rec-png") {
              res.setHeader("content-type", "image/svg+xml");
              return res.end(`<svg xmlns="http://www.w3.org/2000/svg" width="200" height="60"><rect width="200" height="60" fill="#14201b"/><text x="10" y="35" fill="#00ff88" font-family="monospace">sample image</text></svg>`);
            }
            return send(`{\n  "record": "${rec}",\n  "note": "<b>sample</b> evidence text, rendered inert",\n  "selected_pack_bytes": 7092\n}`, "text/plain");
          }
          res.statusCode = 404; send("{}");
        } catch (e) { res.statusCode = 500; send(JSON.stringify({ error: String(e) })); }
      });
    },
  };
}

export default defineConfig({
  base: "./",
  plugins: [devSample()],
  server: {
    host: "127.0.0.1",
    proxy: process.env.PITWALL_DEV_SAMPLE === "1" ? undefined : { "/api": "http://127.0.0.1:18119" },
  },
  build: { outDir: "dist", emptyOutDir: true, target: "es2022", assetsInlineLimit: 0 },
});
