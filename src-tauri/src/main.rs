#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use keyring::Entry;
use serde::Serialize;

#[derive(Serialize)]
struct AppInfo {
  name: String,
  version: String,
  runtime: String
}

#[tauri::command]
fn save_token(profile_id: String, token: String) -> Result<(), String> {
  let service = "clawtty-v4";
  let username = format!("token:{}", profile_id);
  let entry = Entry::new(service, &username).map_err(|e| e.to_string())?;
  entry.set_password(&token).map_err(|e| e.to_string())
}

#[tauri::command]
fn load_token(profile_id: String) -> Result<Option<String>, String> {
  let service = "clawtty-v4";
  let username = format!("token:{}", profile_id);
  let entry = Entry::new(service, &username).map_err(|e| e.to_string())?;
  match entry.get_password() {
    Ok(v) => Ok(Some(v)),
    Err(_) => Ok(None)
  }
}

#[tauri::command]
fn delete_token(profile_id: String) -> Result<(), String> {
  let service = "clawtty-v4";
  let username = format!("token:{}", profile_id);
  let entry = Entry::new(service, &username).map_err(|e| e.to_string())?;
  let _ = entry.delete_credential();
  Ok(())
}

#[tauri::command]
fn app_info() -> AppInfo {
  AppInfo {
    name: "ClawTTY".into(),
    version: env!("CARGO_PKG_VERSION").into(),
    runtime: "tauri-v2".into()
  }
}

#[tauri::command]
fn export_log(path: String, content: String) -> Result<(), String> {
  std::fs::write(path, content).map_err(|e| e.to_string())
}

fn main() {
  tauri::Builder::default()
    .plugin(tauri_plugin_shell::init())
    .plugin(tauri_plugin_dialog::init())
    .invoke_handler(tauri::generate_handler![save_token, load_token, delete_token, app_info, export_log])
    .run(tauri::generate_context!())
    .expect("error while running tauri application");
}
