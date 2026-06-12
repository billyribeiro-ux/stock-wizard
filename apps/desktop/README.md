# Stock Wizard — Desktop (Tauri)

A lightweight desktop shell (Tauri v2) that wraps the same SvelteKit dashboard used on
the web, so Stock Wizard ships as **both web and app** from one UI codebase.

> Status: **scaffold**. The config and Rust entrypoint are in place; building requires the
> Rust toolchain + Tauri CLI (`cargo`, `pnpm dlx @tauri-apps/cli`) which aren't installed in
> the CI sandbox, so it has not been compiled here.

## How it fits together
- **Frontend:** the existing `apps/web` SvelteKit app. For desktop it must be built as static
  assets — add `@sveltejs/adapter-static` (SPA fallback) as a build mode so `apps/web/build`
  contains a static bundle that Tauri loads (`frontendDist` in `src-tauri/tauri.conf.json`).
  Web deployment keeps `adapter-node`; desktop uses the static build. The UI already routes
  all backend calls through a typed client, so it works in either mode.
- **Backend:** the FastAPI engine runs as a **bundled sidecar** process (via
  `tauri-plugin-shell`), with Postgres/Redis either embedded for single-user use or pointed at
  a local/remote instance. The desktop app talks to `http://127.0.0.1:8000` like the web app.

## Build (on a machine with Rust + Node)
```bash
# one-time: add the static build mode to apps/web and install the Tauri CLI
pnpm --dir apps/web add -D @sveltejs/adapter-static
pnpm dlx @tauri-apps/cli@latest dev      # from apps/desktop, dev shell
pnpm dlx @tauri-apps/cli@latest build     # production bundles (dmg/msi/AppImage)
```

## Files
- `src-tauri/tauri.conf.json` — window + build config (frontend dist, dev URL).
- `src-tauri/Cargo.toml` — Rust crate + Tauri deps (`tauri`, `tauri-plugin-shell`).
- `src-tauri/src/main.rs` — app entrypoint.
- `src-tauri/build.rs` — Tauri build script.
- `src-tauri/icons/` — app icons (add via `tauri icon path/to/logo.png`).
