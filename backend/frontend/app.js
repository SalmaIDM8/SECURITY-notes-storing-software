// ---- Config ----
const API_BASE = ""; // same-origin. If backend runs elsewhere: "http://127.0.0.1:8000"

// ---- State ----
let state = {
  userId: null,
  token: null,
  notes: [],
  selectedNote: null,
  lockId: null,

  // shared note flow
  shared: {
    shareId: null,
    note: null,
    lockId: null,
  }
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

// ---- Token storage (sessionStorage, safer than localStorage) ----
function saveSession() {
  if (state.token && state.userId) {
    sessionStorage.setItem("sn_token", state.token);
    sessionStorage.setItem("sn_user", state.userId);
  } else {
    sessionStorage.removeItem("sn_token");
    sessionStorage.removeItem("sn_user");
  }
}

function loadSession() {
  state.token = sessionStorage.getItem("sn_token");
  state.userId = sessionStorage.getItem("sn_user");
}

// ---- HTTP ----
async function api(path, { method = "GET", body = null, auth = true } = {}) {
  const headers = { "Content-Type": "application/json" };

  // Prefer JWT; for dev compatibility, backend might still support X-User-Id in places.
  if (auth && state.token) headers["Authorization"] = `Bearer ${state.token}`;
  if (auth && !state.token && state.userId) headers["X-User-Id"] = state.userId;

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : null,
  });

  const contentType = res.headers.get("content-type") || "";
  const data = contentType.includes("application/json") ? await res.json() : await res.text();

    if (!res.ok) {
    if (typeof data === "object") {
      throw new Error(`${res.status} ${JSON.stringify(data)}`);
    }
    throw new Error(`${res.status} ${data}`);
  }

  return data;
}

// ---- Auth ----
async function register() {
  setMsg("authMsg", "");
  const user_id = $("userId").value.trim();
  const password = $("password").value;

  if (!user_id || !password) return setMsg("authMsg", "Please enter user_id and password.", true);

  try {
    await api("/auth/register", { method: "POST", body: { user_id, password }, auth: false });
    setMsg("authMsg", "Registered successfully. Now login.", false);
  } catch (e) {
    setMsg("authMsg", e.message, true);
  }
}

async function login() {
  setMsg("authMsg", "");
  const user_id = $("userId").value.trim();
  const password = $("password").value;

  if (!user_id || !password) return setMsg("authMsg", "Please enter user_id and password.", true);

  try {
    const data = await api("/auth/login", { method: "POST", body: { user_id, password }, auth: false });
    state.token = data.access_token;
    state.userId = user_id;
    saveSession();
    setWhoami();
    hide($("authView"));
    show($("appView"));
    setMsg("appMsg", "");
    await refreshNotes();
  } catch (e) {
    setMsg("authMsg", e.message, true);
  }
}

function logout() {
  state = { userId: null, token: null, notes: [], selectedNote: null, lockId: null, shared: { shareId: null, note: null, lockId: null } };
  saveSession();
  setWhoami();
  $("notesList").innerHTML = "";
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
  list.innerHTML = "";

  const filtered = state.notes.filter(n => !q || (n.title || "").toLowerCase().includes(q));
  filtered.forEach(note => {
    const li = document.createElement("li");
    li.textContent = `${note.title}  (v${note.version})`;
    li.className = (state.selectedNote && state.selectedNote.id === note.id) ? "active" : "";
    li.onclick = () => selectNote(note.id);
    list.appendChild(li);
  });

  if (filtered.length === 0) {
    const li = document.createElement("li");
    li.textContent = "No notes.";
    li.className = "muted";
    list.appendChild(li);
  }
}

async function refreshNotes() {
  setMsg("appMsg", "");
  try {
    const notes = await api("/notes");
    state.notes = notes;
    renderNotesList();
  } catch (e) {
    setMsg("appMsg", e.message, true);
  }
}

async function selectNote(noteId) {
  setMsg("appMsg", "");
  state.lockId = null;
  setLockPill("No lock", false);

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
  }
}

async function newNote() {
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

  try {
    const note = await api("/notes", { method: "POST", body: { title, content } });
    setMsg("appMsg", "Note created.", false);
    await refreshNotes();
    await selectNote(note.id);
  } catch (e) {
    setMsg("appMsg", e.message, true);
  }
}

async function acquireLock() {
  setMsg("appMsg", "");
  if (!state.selectedNote) return setMsg("appMsg", "Select a note first.", true);

  try {
    const data = await api(`/notes/${state.selectedNote.id}/lock`, { method: "POST" });
    state.lockId = data.lock_id;
    setLockPill(`Locked (${state.lockId})`, true);
    setMsg("appMsg", "Lock acquired.", false);
  } catch (e) {
    setMsg("appMsg", e.message, true);
  }
}

async function releaseLock() {
  setMsg("appMsg", "");
  if (!state.selectedNote) return setMsg("appMsg", "Select a note first.", true);

  try {
    await api(`/notes/${state.selectedNote.id}/lock`, { method: "DELETE" });
    state.lockId = null;
    setLockPill("No lock", false);
    setMsg("appMsg", "Lock released.", false);
  } catch (e) {
    setMsg("appMsg", e.message, true);
  }
}

async function saveNote() {
  setMsg("appMsg", "");

  const title = $("noteTitle").value.trim();
  const content = $("noteContent").value;

  if (!title) return setMsg("appMsg", "Title is required.", true);

  // If no note selected -> create
  if (!state.selectedNote) return createNote();

  if (!state.lockId) return setMsg("appMsg", "Acquire a lock before saving.", true);

  try {
    const updated = await api(`/notes/${state.selectedNote.id}`, {
      method: "PUT",
      body: { title, content, lock_id: state.lockId }
    });
    setMsg("appMsg", "Saved.", false);
    await refreshNotes();
    await selectNote(updated.id);
  } catch (e) {
    setMsg("appMsg", e.message, true);
  }
}

// ---- Sharing (owner creates shares; recipient uses share_id) ----
async function createShare() {
  setMsg("appMsg", "");
  if (!state.selectedNote) return setMsg("appMsg", "Select a note to share.", true);

  const shared_with_user_id = $("shareWith").value.trim();
  const mode = $("shareMode").value;

  if (!shared_with_user_id) return setMsg("appMsg", "Enter shared_with_user_id.", true);

  try {
    const s = await api(`/shares/notes/${state.selectedNote.id}`, {
      method: "POST",
      body: { shared_with_user_id, mode }
    });
    $("shareId").value = s.share_id;
    setMsg("appMsg", `Share created: ${s.share_id} (${s.mode})`, false);
  } catch (e) {
    setMsg("appMsg", e.message, true);
  }
}

async function revokeShare() {
  setMsg("appMsg", "");
  const share_id = $("shareId").value.trim();
  if (!share_id) return setMsg("appMsg", "Paste a share_id to revoke.", true);

  try {
    await api(`/shares/${share_id}/revoke`, { method: "POST" });
    setMsg("appMsg", "Share revoked.", false);
  } catch (e) {
    setMsg("appMsg", e.message, true);
  }
}

// Recipient opens share note
async function openShare() {
  setMsg("appMsg", "");
  const share_id = $("shareId").value.trim();
  if (!share_id) return setMsg("appMsg", "Paste share_id first.", true);

  try {
    const note = await api(`/shares/${share_id}`, { method: "GET" });
    state.shared.shareId = share_id;
    state.shared.note = note;
    state.shared.lockId = null;

    // show in editor (read-only-ish, but we’ll allow save via Share buttons)
    $("noteTitle").value = note.title || "";
    $("noteContent").value = note.content || "";
    $("noteVersion").value = String(note.version || "");
    $("editorTitle").textContent = `Shared note via ${share_id}`;
    setLockPill("Shared: no lock", false);
    setMsg("appMsg", "Shared note loaded.", false);
  } catch (e) {
    setMsg("appMsg", e.message, true);
  }
}

async function shareLock() {
  setMsg("appMsg", "");
  const share_id = $("shareId").value.trim();
  if (!share_id) return setMsg("appMsg", "Paste share_id first.", true);

  try {
    const lock = await api(`/shares/${share_id}/lock`, { method: "POST" });
    state.shared.lockId = lock.lock_id;
    setLockPill(`Shared lock (${state.shared.lockId})`, true);
    setMsg("appMsg", "Shared lock acquired.", false);
  } catch (e) {
    setMsg("appMsg", e.message, true);
  }
}

async function shareSave() {
  setMsg("appMsg", "");
  const share_id = $("shareId").value.trim();
  if (!share_id) return setMsg("appMsg", "Paste share_id first.", true);

  if (!state.shared.lockId) return setMsg("appMsg", "Acquire shared lock first (RW only).", true);

  const title = $("noteTitle").value.trim();
  const content = $("noteContent").value;

  try {
    const updated = await api(`/shares/${share_id}`, {
      method: "PUT",
      body: { title, content, lock_id: state.shared.lockId }
    });
    $("noteVersion").value = String(updated.version || "");
    setMsg("appMsg", "Shared note saved.", false);
  } catch (e) {
    setMsg("appMsg", e.message, true);
  }
}

// ---- Wire up ----
function bind() {
  $("registerBtn").onclick = register;
  $("loginBtn").onclick = login;
  $("logoutBtn").onclick = logout;

  $("refreshBtn").onclick = refreshNotes;
  $("searchBox").oninput = renderNotesList;
  $("newNoteBtn").onclick = newNote;

  $("acquireLockBtn").onclick = acquireLock;
  $("saveBtn").onclick = saveNote;
  $("releaseLockBtn").onclick = releaseLock;

  $("createShareBtn").onclick = createShare;
  $("revokeShareBtn").onclick = revokeShare;

  $("openShareBtn").onclick = openShare;
  $("shareLockBtn").onclick = shareLock;
  $("shareSaveBtn").onclick = shareSave;

  // Convenience: Enter triggers login when on auth view
  $("password").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !$("authView").classList.contains("hidden")) login();
  });
}

function init() {
  bind();
  loadSession();
  setWhoami();

  if (state.token && state.userId) {
    hide($("authView"));
    show($("appView"));
    refreshNotes();
  } else {
    show($("authView"));
    hide($("appView"));
  }
}

init();
