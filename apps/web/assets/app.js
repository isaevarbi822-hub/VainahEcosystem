import { bootApps, showApp } from "./suite-ui.js";
// Vanilla JS, no external dependencies: minimal, testable first-stage web app.
const apps = [
  { name: 'AI', icon: '✦', desc: 'ИИ через подключаемую модель', ready: true },
  { name: 'Messenger', ready: true, icon: '◉', desc: 'Разговоры и сообщества' },
  { name: 'Browser', ready: true, icon: '◎', desc: 'Интернет по-вашему' },
  { name: 'Music', ready: true, icon: '♫', desc: 'Любимая музыка' },
  { name: 'Weather', ready: true, icon: '☁', desc: 'Погода в вашем городе' },
  { name: 'Maps', ready: true, icon: '⌖', desc: 'Карта вашего мира' },
  { name: 'Notes', icon: '▤', desc: 'Мысли и идеи', ready: true },
  { name: 'Translate', ready: true, icon: '文', desc: 'Языки без барьеров' },
  { name: 'Study', ready: true, icon: '▣', desc: 'Учитесь по-своему' },
  { name: 'Photos', ready: true, icon: '▧', desc: 'Ваши воспоминания' },
  { name: 'Calendar', ready: true, icon: '▦', desc: 'Планы на каждый день' },
];

const $ = (id) => document.getElementById(id);
const state = { user: null, csrf: '', notes: [], selected: null, mode: 'login', screen: 'home', noteDirty: false };
let toastTimer;

function showToast(message) {
  $('toast').textContent = message;
  $('toast').classList.remove('hidden');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => $('toast').classList.add('hidden'), 3200);
}

async function api(path, { method = 'GET', body } = {}) {
  const headers = {};
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (!['GET', 'HEAD'].includes(method) && state.csrf) headers['X-CSRF-Token'] = state.csrf;
  let response;
  try {
    response = await fetch(path, { method, headers, credentials: 'same-origin', body: body === undefined ? undefined : JSON.stringify(body) });
  } catch {
    throw new Error('Нет связи с сервером. Проверьте подключение.');
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data.detail;
    const message = typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map((x) => x.msg).join('; ') : 'Ошибка запроса';
    throw new Error(message);
  }
  return data;
}

function setAuthMode(mode) {
  state.mode = mode;
  const signUp = mode === 'register';
  $('name-group').classList.toggle('hidden', !signUp);
  $('invite-group').classList.toggle('hidden', !signUp);
  $('signup-name').required = signUp;
  $('password').autocomplete = signUp ? 'new-password' : 'current-password';
  $('form-heading').textContent = signUp ? 'Создайте свой Vainah ID' : 'С возвращением';
  $('form-subheading').textContent = signUp ? 'Один аккаунт для всех приложений Vainah.' : 'Войдите, чтобы открыть вашу экосистему.';
  $('auth-submit').firstChild.textContent = signUp ? 'Создать аккаунт ' : 'Войти ';
  $('switch-question').textContent = signUp ? 'Уже есть аккаунт?' : 'Ещё нет аккаунта?';
  $('auth-mode-toggle').textContent = signUp ? 'Войти' : 'Создать Vainah ID';
  $('auth-error').classList.add('hidden');
}

async function submitAuth(event) {
  event.preventDefault();
  const button = $('auth-submit');
  button.disabled = true;
  $('auth-error').classList.add('hidden');
  const payload = { email: $('email').value, password: $('password').value };
  if (state.mode === 'register') { payload.display_name = $('signup-name').value; payload.invite_code = $('signup-invite').value || null; }
  try {
    const result = await api(`/api/auth/${state.mode === 'register' ? 'register' : 'login'}`, { method: 'POST', body: payload });
    state.user = result.user;
    state.csrf = result.csrf_token;
    $('password').value = '';
    await showWorkspace();
  } catch (error) {
    $('auth-error').textContent = error.message;
    $('auth-error').classList.remove('hidden');
  } finally {
    button.disabled = false;
  }
}

function renderAppCards(target, limit, query='') {
  target.replaceChildren();
  for (const item of apps.filter(x => (x.name + ' ' + x.desc).toLocaleLowerCase().includes(query.toLocaleLowerCase())).slice(0, limit || apps.length)) {
    const card = document.createElement('button');
    card.type = 'button';
    card.className = `app-card ${item.ready ? 'ready' : 'soon'}`;
    card.disabled = !item.ready;
    const symbol = document.createElement('span'); symbol.className = 'app-icon'; symbol.textContent = item.icon;
    const title = document.createElement('strong'); title.textContent = `Vainah ${item.name}`;
    const desc = document.createElement('span'); desc.className = 'app-desc'; desc.textContent = item.desc;
    const status = document.createElement('span'); status.className = `app-status ${item.ready ? 'live' : ''}`; status.textContent = item.ready ? 'Доступно' : 'Скоро';
    card.append(symbol, title, desc, status);
    if (item.ready) card.addEventListener('click', () => navigate(item.name.toLowerCase()));
    target.append(card);
  }
}

function navigate(screen) {
  if (screen !== state.screen && state.noteDirty && !window.confirm('Изменения заметки не сохранены. Продолжить без сохранения?')) return;
  if (screen !== state.screen) state.noteDirty = false;
  state.screen = screen;
  for (const name of ['home', 'notes', 'apps', 'settings']) $(`screen-${name}`).classList.toggle('hidden', name !== screen);
  $('screen-feature').classList.toggle('hidden', ['home','notes','apps','settings'].includes(screen));
  document.querySelectorAll('[data-screen]').forEach((node) => node.classList.toggle('active', node.dataset.screen === screen));
  $('breadcrumb-name').textContent = { home: 'Обзор', notes: 'Заметки', apps: 'Приложения', settings: 'Настройки' }[screen] || 'Vainah ' + screen;
  if (screen === 'notes') loadNotes().catch(error => showToast(error.message));
  if (!['home','notes','apps','settings'].includes(screen)) showApp(screen, { api, state, showToast });
}

function prettyTime(ts) {
  return new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short' }).format(new Date(ts * 1000));
}

async function loadNotes() {
  const result = await api('/api/notes');
  state.notes = result.items;
  $('notes-count').textContent = String(state.notes.length);
  renderNotes();
}

function renderNotes() {
  const list = $('notes-list');
  const search = $('search-notes').value.toLocaleLowerCase();
  const filtered = state.notes.filter((note) => (note.title + ' ' + note.content).toLocaleLowerCase().includes(search));
  list.replaceChildren();
  if (filtered.length === 0) {
    const empty = document.createElement('p'); empty.className = 'list-empty';
    empty.textContent = search ? 'Ничего не найдено.' : 'Здесь пока нет заметок. Создайте первую!';
    list.append(empty);
  }
  for (const note of filtered) {
    const button = document.createElement('button');
    button.type = 'button'; button.className = `note-item ${state.selected === note.id ? 'active' : ''}`;
    const title = document.createElement('strong'); title.textContent = note.title || 'Без названия';
    const preview = document.createElement('span'); preview.textContent = `${prettyTime(note.updated_at)} · ${note.content.slice(0, 65) || 'Пустая заметка'}`;
    button.append(title, preview); button.addEventListener('click', () => selectNote(note.id)); list.append(button);
  }
  const note = state.notes.find((n) => n.id === state.selected);
  $('editor').classList.toggle('hidden', !note);
  $('editor-empty').classList.toggle('hidden', Boolean(note));
}

function selectNote(id) {
  if (id !== state.selected && state.noteDirty && !window.confirm('Не сохранять изменения заметки?')) return;
  state.noteDirty = false;
  state.selected = id;
  const note = state.notes.find((n) => n.id === id);
  if (!note) return renderNotes();
  $('note-title').value = note.title;
  $('note-content').value = note.content;
  $('note-status').textContent = `Последнее сохранение: ${prettyTime(note.updated_at)} · Сохраните изменения кнопкой`;
  renderNotes();
}

async function createNote() {
  if (state.noteDirty && !window.confirm('Есть несохранённые изменения. Создать заметку без их сохранения?')) return;
  state.noteDirty = false;
  try {
    const note = await api('/api/notes', { method: 'POST', body: { title: 'Новая заметка', content: '' } });
    state.notes.unshift(note);
    state.selected = note.id;
    $('search-notes').value = '';
    selectNote(note.id);
    $('notes-count').textContent = String(state.notes.length);
    $('note-title').focus();
    showToast('Заметка создана');
  } catch (error) { showToast(error.message); }
}

async function saveNote() {
  if (!state.selected) return;
  const button = $('save-note'); button.disabled = true;
  try {
    const updated = await api(`/api/notes/${encodeURIComponent(state.selected)}`, { method: 'PUT', body: { title: $('note-title').value, content: $('note-content').value } });
    const i = state.notes.findIndex((n) => n.id === updated.id);
    if (i >= 0) state.notes[i] = updated;
    state.noteDirty = false; $('note-status').textContent = 'Сохранено ✓'; renderNotes(); showToast('Изменения сохранены');
  } catch (error) { showToast(error.message); }
  finally { button.disabled = false; }
}

async function deleteNote() {
  if (!state.selected || !window.confirm('Удалить эту заметку без возможности восстановления?')) return;
  try {
    await api(`/api/notes/${encodeURIComponent(state.selected)}`, { method: 'DELETE' });
    state.noteDirty = false;
    state.notes = state.notes.filter((n) => n.id !== state.selected);
    state.selected = null;
    $('notes-count').textContent = String(state.notes.length);
    renderNotes(); showToast('Заметка удалена');
  } catch (error) { showToast(error.message); }
}

async function showWorkspace() {
  $('login-view').classList.add('hidden'); $('workspace').classList.remove('hidden');
  const name = state.user.display_name;
  $('sidebar-name').textContent = name; $('sidebar-email').textContent = state.user.email;
  $('avatar').textContent = $('top-avatar').textContent = name.slice(0, 1).toUpperCase();
  $('hello').textContent = `Привет, ${name}!`;
  $('profile-name').value = name; $('profile-email').value = state.user.email;
  const match = location.pathname.match(/^\/app\/(ai|messenger|browser|music|weather|maps|notes|translate|study|photos|calendar)$/);
  navigate(match ? match[1] : 'home');
  try { await loadNotes(); } catch (error) { showToast(error.message); }
}

async function restoreSession() {
  try {
    const result = await api('/api/auth/me');
    state.user = result.user; state.csrf = result.csrf_token;
    await showWorkspace();
  } catch {
    $('workspace').classList.add('hidden'); $('login-view').classList.remove('hidden');
  }
}

function registerHandlers() {
  renderAppCards($('home-apps'), 8);
  renderAppCards($('all-apps'));
  bootApps({ navigate });
  $('auth-form').addEventListener('submit', submitAuth);
  $('auth-mode-toggle').addEventListener('click', () => setAuthMode(state.mode === 'login' ? 'register' : 'login'));
  document.querySelectorAll('[data-screen]').forEach((b) => b.addEventListener('click', () => navigate(b.dataset.screen)));
  document.querySelectorAll('[data-open-notes]').forEach((b) => b.addEventListener('click', () => navigate('notes')));
  $('show-all').addEventListener('click', () => navigate('apps'));
  $('create-note').addEventListener('click', createNote);
  $('save-note').addEventListener('click', saveNote);
  $('delete-note').addEventListener('click', deleteNote);
  $('search-notes').addEventListener('input', renderNotes);
  $('search-apps').addEventListener('input', () => renderAppCards($('all-apps'), null, $('search-apps').value.trim()));
  document.addEventListener('keydown', (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault(); navigate('apps'); $('search-apps').focus();
    }
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's' && state.screen === 'notes') {
      event.preventDefault(); saveNote();
    }
  });
  $('profile-form').addEventListener('submit', async event => {
    event.preventDefault();
    try {
      const result = await api('/api/auth/profile', { method: 'PATCH', body: { display_name: $('profile-name').value } });
      state.user = result.user; $('sidebar-name').textContent = result.user.display_name;
      $('avatar').textContent = $('top-avatar').textContent = result.user.display_name.slice(0, 1).toUpperCase();
      $('hello').textContent = `Привет, ${result.user.display_name}!`; showToast('Профиль обновлён');
    } catch(error) { showToast(error.message); }
  });
  $('password-form').addEventListener('submit', async event => {
    event.preventDefault();
    try {
      await api('/api/auth/password', { method: 'POST', body: {
        current_password: $('current-password').value, new_password: $('new-password').value
      }});
      $('password-form').reset(); showToast('Пароль изменён. Другие сеансы завершены.');
    } catch(error) { showToast(error.message); }
  });
  $('logout-others').addEventListener('click', async () => {
    try { const result = await api('/api/auth/logout-others', {method:'POST'});
      showToast(`Завершено других сеансов: ${result.revoked_sessions}`);
    } catch(error) { showToast(error.message); }
  });
  $('note-content').addEventListener('input', () => { state.noteDirty = true; $('note-status').textContent = 'Есть несохранённые изменения'; });
  $('note-title').addEventListener('input', () => { state.noteDirty = true; $('note-status').textContent = 'Есть несохранённые изменения'; });
  $('logout').addEventListener('click', async () => {
    try { await api('/api/auth/logout', { method: 'POST' }); } catch (error) { showToast(error.message); return; }
    state.user = null; state.csrf = ''; state.notes = []; state.selected = null; state.noteDirty = false;
    $('workspace').classList.add('hidden'); $('login-view').classList.remove('hidden');
  });
}

registerHandlers();
restoreSession();

// Native install on supported browsers when hosted on HTTPS (Android/desktop).
if ('serviceWorker' in navigator && (location.protocol === 'https:' || location.hostname === 'localhost')) {
  window.addEventListener('load', () => navigator.serviceWorker.register('/sw.js').catch(() => {}));
}
