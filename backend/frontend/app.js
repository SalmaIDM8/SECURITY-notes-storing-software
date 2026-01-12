// ---- Config ----
const API_BASE = "http://127.0.0.1:8000";

// If true, the UI will rely on HttpOnly cookies (credentials: include) and will NOT use Authorization headers.
// (We’ll enable this once the backend exposes /auth/login_cookie).
const USE_COOKIE_AUTH = true;

// ---- State ----
let state = {
  userId: null,
  token: null, // kept only in memory (no storage)
  notes: [],
  selectedNote: null,
  lockId: null,
  shared: { shareId: null, note: null, lockId: null },
};

// ---- DOM helpers ----
const $ = (id) => document.getElementById(id);
const show = (el) => el.classList.remove("hidden");
const hide = (el) => el.classList.add("hidden");

function setMsg(targetId, text, isError = false) {
  const el = $(targetId);
  el.textContent = text || "";
  el.style.color = isError ? "#ff9aa8" : "#ffd08a";
}

function setWhoami() {
  $("whoami").textContent = state.userId ? `Logged in as: ${state.userId}` : "";
  state.userId ? show($("logoutBtn")) : hide($("logoutBtn"));
}

function setLockPill(text, ok) {
  const pill = $("lockState");
  pill.textContent = text;
  pill.classList.toggle("muted", !ok);
}

function setBusy(isBusy) {
  const ids = [
    "loginBtn","registerBtn","logoutBtn",
    "refreshBtn","newNoteBtn","acquireLockBtn","saveBtn","releaseLockBtn",
    "createShareBtn","revokeShareBtn","openShareBtn","shareLockBtn","shareSaveBtn"
  ];
  ids.forEach((id) => {
    const el = $(id);
    if (el) el.disabled = !!isBusy;
  });
}

// ---- HTTP ----
async function api(path, { method = "GET", body = null, auth = true } = {}) {
  const headers = { "Content-Type": "application/json" };

  // Auth strategy:
  // - If cookie auth enabled: rely on cookies only (credentials include)
  // - Else: use Bearer token in memory; fallback X-User-Id when no token
  if (auth && !USE_COOKIE_AUTH) {
    if (state.token) headers["Authorization"] = `Bearer ${state.token}`;
    else if (state.userId) headers["X-User-Id"] = state.userId;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    credentials: "include", // important for future HttpOnly cookie auth
    body: body ? JSON.stringify(body) : null,
  });

  const contentType = res.headers.get("content-type") || "";
  let data;
  try {
    data = contentType.includes("application/json") ? await res.json() : await res.text();
  } catch {
    data = await res.text().catch(() => "");
  }

  if (!res.ok) {
    const msg = typeof data === "object" ? JSON.stringify(data) : String(data || "");
    throw new Error(`${res.status} ${msg}`.trim());
  }

  return data;
}

// ---- Auth ----
async function register() {
  setMsg("authMsg", "");
  const user_id = $("userId").value.trim();
  const password = $("password").value;

  if (!user_id || !password) return setMsg("authMsg", "Please enter user_id and password.", true);

  setBusy(true);
  try {
    await api("/auth/register", { method: "POST", body: { user_id, password }, auth: false });
    setMsg("authMsg", "Registered successfully. Now login.", false);
  } catch (e) {
    setMsg("authMsg", e.message, true);
  } finally {
    setBusy(false);
  }
}

async function login() {
  setMsg("authMsg", "");
  const user_id = $("userId").value.trim();
  const password = $("password").value;

  if (!user_id || !password) return setMsg("authMsg", "Please enter user_id and password.", true);

  setBusy(true);
  try {
    if (USE_COOKIE_AUTH) {
      // Future: backend will provide /auth/login_cookie (sets HttpOnly cookie)
      await api("/auth/login_cookie", { method: "POST", body: { user_id, password }, auth: false });
      state.token = null;
    } else {
      const data = await api("/auth/login", { method: "POST", body: { user_id, password }, auth: false });
      state.token = data.access_token; // memory only
    }

    state.userId = user_id;
    setWhoami();

    hide($("authView"));
    show($("appView"));
    setMsg("appMsg", "");
    await refreshNotes();
  } catch (e) {
    setMsg("authMsg", e.message, true);
  } finally {
    setBusy(false);
  }
}

function logout() {
  state = {
    userId: null,
    token: null,
    notes: [],
    selectedNote: null,
    lockId: null,
    shared: { shareId: null, note: null, lockId: null },
  };

  setWhoami();
  $("notesList").replaceChildren();
  $("noteTitle").value = "";
  $("noteContent").value = "";
  $("noteVersion").value = "";
  $("shareId").value = "";
  setLockPill("No lock", false);

  show($("authView"));
  hide($("appView"));
  setMsg("authMsg", "Logged out.", false);
}

// ---- Notes list + editor ----
function renderNotesList() {
  const q = $("searchBox").value.trim().toLowerCase();
  const list = $("notesList");
  list.replaceChildren();

  const filtered = state.notes.filter((n) => !q || (n.title || "").toLowerCase().includes(q));

  if (filtered.length === 0) {
    const li = document.createElement("li");
    li.textContent = "No notes.";
    li.className = "muted";
    list.appendChild(li);
    return;
  }

  filtered.forEach((note) => {
    const li = document.createElement("li");
    li.textContent = `${note.title}  (v${note.version})`;
    li.className = state.selectedNote && state.selectedNote.id === note.id ? "active" : "";
    li.addEventListener("click", () => selectNote(note.id));
    list.appendChild(li);
  });
}

async function refreshNotes() {
  setMsg("appMsg", "");
  setBusy(true);
  try {
    const notes = await api("/notes");
    state.notes = notes;
    renderNotesList();
  } catch (e) {
    setMsg("appMsg", e.message, true);
  } finally {
    setBusy(false);
  }
}

async function selectNote(noteId) {
  setMsg("appMsg", "");
  state.lockId = null;
  setLockPill("No lock", false);

  setBusy(true);
  try {
    const note = await api(`/notes/${noteId}`);
    state.selectedNote = note;

    $("noteTitle").value = note.title || "";
    $("noteContent").value = note.content || "";
    $("noteVersion").value = String(note.version || "");
    $("editorTitle").textContent = `Editor: ${note.id}`;

    renderNotesList();
  } catch (e) {
    setMsg("appMsg", e.message, true);
  } finally {
    setBusy(false);
  }
}

function newNote() {
  setMsg("appMsg", "");
  state.selectedNote = null;
  state.lockId = null;
  setLockPill("No lock", false);

  $("noteTitle").value = "";
  $("noteContent").value = "";
  $("noteVersion").value = "";
  $("editorTitle").textContent = "Editor: new note";
}

async function createNote() {
  setMsg("appMsg", "");
  const title = $("noteTitle").value.trim();
  const content = $("noteContent").value;

  if (!title) return setMsg("appMsg", "Title is required.", true);

  setBusy(true);
  try {
    const note = await api("/notes", { method: "POST", body: { title, content } });
    setMsg("appMsg", "Note created.", false);
    await refreshNotes();
    await selectNote(note.id);
  } catch (e) {
    setMsg("appMsg", e.message, true);
  } finally {
    setBusy(false);
  }
}

async function acquireLock() {
  setMsg("appMsg", "");
  if (!state.selectedNote) return setMsg("appMsg", "Select a note first.", true);

  setBusy(true);
  try {
    const data = await api(`/notes/${state.selectedNote.id}/lock`, { method: "POST" });
    state.lockId = data.lock_id;
    setLockPill(`Locked (${state.lockId})`, true);
    setMsg("appMsg", "Lock acquired.", false);
  } catch (e) {
    setMsg("appMsg", e.message, true);
  } finally {
    setBusy(false);
  }
}

async function releaseLock() {
  setMsg("appMsg", "");
  if (!state.selectedNote) return setMsg("appMsg", "Select a note first.", true);

  setBusy(true);
  try {
    await api(`/notes/${state.selectedNote.id}/lock`, { method: "DELETE" });
    state.lockId = null;
    setLockPill("No lock", false);
    setMsg("appMsg", "Lock released.", false);
  } catch (e) {
    setMsg("appMsg", e.message, true);
  } finally {
    setBusy(false);
  }
}

async function saveNote() {
  setMsg("appMsg", "");
  const title = $("noteTitle").value.trim();
  const content = $("noteContent").value;

  if (!title) return setMsg("appMsg", "Title is required.", true);

  if (!state.selectedNote) return createNote();
  if (!state.lockId) return setMsg("appMsg", "Acquire a lock before saving.", true);

  setBusy(true);
  try {
    const updated = await api(`/notes/${state.selectedNote.id}`, {
      method: "PUT",
      body: { title, content, lock_id: state.lockId },
    });
    setMsg("appMsg", "Saved.", false);
    await refreshNotes();
    await selectNote(updated.id);
  } catch (e) {
    setMsg("appMsg", e.message, true);
  } finally {
    setBusy(false);
  }
}

// ---- Sharing ----
async function createShare() {
  setMsg("appMsg", "");
  if (!state.selectedNote) return setMsg("appMsg", "Select a note to share.", true);

  const shared_with_user_id = $("shareWith").value.trim();
  const mode = $("shareMode").value;

  if (!shared_with_user_id) return setMsg("appMsg", "Enter shared_with_user_id.", true);

  setBusy(true);
  try {
    const s = await api(`/shares/notes/${state.selectedNote.id}`, {
      method: "POST",
      body: { shared_with_user_id, mode },
    });
    $("shareId").value = s.share_id;
    setMsg("appMsg", `Share created: ${s.share_id} (${s.mode})`, false);
  } catch (e) {
    setMsg("appMsg", e.message, true);
  } finally {
    setBusy(false);
  }
}

async function revokeShare() {
  setMsg("appMsg", "");
  const share_id = $("shareId").value.trim();
  if (!share_id) return setMsg("appMsg", "Paste a share_id to revoke.", true);

  // small safety UX
  if (!confirm("Revoke this share? Recipients will lose access.")) return;

  setBusy(true);
  try {
    await api(`/shares/${share_id}/revoke`, { method: "POST" });
    setMsg("appMsg", "Share revoked.", false);
  } catch (e) {
    setMsg("appMsg", e.message, true);
  } finally {
    setBusy(false);
  }
}

async function openShare() {
  setMsg("appMsg", "");
  const share_id = $("shareId").value.trim();
  if (!share_id) return setMsg("appMsg", "Paste share_id first.", true);

  setBusy(true);
  try {
    const note = await api(`/shares/${share_id}`, { method: "GET" });
    state.shared.shareId = share_id;
    state.shared.note = note;
    state.shared.lockId = null;

    $("noteTitle").value = note.title || "";
    $("noteContent").value = note.content || "";
    $("noteVersion").value = String(note.version || "");
    $("editorTitle").textContent = `Shared note via ${share_id}`;
    setLockPill("Shared: no lock", false);

    setMsg("appMsg", "Shared note loaded.", false);
  } catch (e) {
    setMsg("appMsg", e.message, true);
  } finally {
    setBusy(false);
  }
}

async function shareLock() {
  setMsg("appMsg", "");
  const share_id = $("shareId").value.trim();
  if (!share_id) return setMsg("appMsg", "Paste share_id first.", true);

  setBusy(true);
  try {
    const lock = await api(`/shares/${share_id}/lock`, { method: "POST" });
    state.shared.lockId = lock.lock_id;
    setLockPill(`Shared lock (${state.shared.lockId})`, true);
    setMsg("appMsg", "Shared lock acquired.", false);
  } catch (e) {
    setMsg("appMsg", e.message, true);
  } finally {
    setBusy(false);
  }
}

async function shareSave() {
  setMsg("appMsg", "");
  const share_id = $("shareId").value.trim();
  if (!share_id) return setMsg("appMsg", "Paste share_id first.", true);
  if (!state.shared.lockId) return setMsg("appMsg", "Acquire shared lock first (RW only).", true);

  const title = $("noteTitle").value.trim();
  const content = $("noteContent").value;

  setBusy(true);
  try {
    const updated = await api(`/shares/${share_id}`, {
      method: "PUT",
      body: { title, content, lock_id: state.shared.lockId },
    });
    $("noteVersion").value = String(updated.version || "");
    setMsg("appMsg", "Shared note saved.", false);
  } catch (e) {
    setMsg("appMsg", e.message, true);
  } finally {
    setBusy(false);
  }
}

// ---- Wire up ----
function bind() {
  $("registerBtn").addEventListener("click", register);
  $("loginBtn").addEventListener("click", login);
  $("logoutBtn").addEventListener("click", logout);

  $("refreshBtn").addEventListener("click", refreshNotes);
  $("searchBox").addEventListener("input", renderNotesList);
  $("newNoteBtn").addEventListener("click", newNote);

  $("acquireLockBtn").addEventListener("click", acquireLock);
  $("saveBtn").addEventListener("click", saveNote);
  $("releaseLockBtn").addEventListener("click", releaseLock);

  $("createShareBtn").addEventListener("click", createShare);
  $("revokeShareBtn").addEventListener("click", revokeShare);

  $("openShareBtn").addEventListener("click", openShare);
  $("shareLockBtn").addEventListener("click", shareLock);
  $("shareSaveBtn").addEventListener("click", shareSave);

  $("password").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !$("authView").classList.contains("hidden")) login();
  });
}

function init() {
  bind();
  setWhoami();

  // No session restore by design (AR-4 prep): token is not persisted.
  show($("authView"));
  hide($("appView"));
}

document.addEventListener("DOMContentLoaded", init);
