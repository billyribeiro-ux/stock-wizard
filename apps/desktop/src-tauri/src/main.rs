// Stock Wizard desktop shell (Tauri v2).
//
// Wraps the SvelteKit dashboard. In production the FastAPI engine is shipped as a
// bundled sidecar (configured via tauri-plugin-shell); during development point the
// app at the running `just api` + `pnpm dev` servers (see tauri.conf.json devUrl).
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .run(tauri::generate_context!())
        .expect("error while running Stock Wizard desktop");
}
