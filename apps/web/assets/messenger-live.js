/* Vainah Messenger 0.7: real-time updates, opt-in foreground notifications and
   WebRTC preview calls. No server-stored SDP, no background push, no TURN relay. */
export function createMessengerRealtime({ stage, state, active, getContact, onUpdate, toast, chats }) {
  const el = (tag, className = '', content = '') => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    node.textContent = content;
    return node;
  };
  const panel = el('div', 'vcall-panel hidden');
  panel.setAttribute('role', 'status');
  panel.setAttribute('aria-live', 'polite');
  const label = el('div', 'vcall-label', 'Звонок');
  const mediaBox = el('div', 'vcall-media');
  const remote = el('video', 'vcall-remote');
  const local = el('video', 'vcall-local');
  remote.autoplay = local.autoplay = true;
  remote.playsInline = local.playsInline = true;
  local.muted = true;
  mediaBox.append(remote, local);
  const buttons = el('div', 'vcall-buttons');
  const accept = el('button', 'primary', 'Ответить');
  const decline = el('button', 'secondary-btn', 'Отклонить');
  const hang = el('button', 'danger-button', 'Завершить');
  [accept, decline, hang].forEach(b => { b.type = 'button'; buttons.append(b); });
  panel.append(label, mediaBox, buttons);
  stage.parentElement.append(panel);

  const status = el('span', 'vchat-live-state', '● Подключение…');
  const notifications = el('button', 'vchat-soft', '🔔 Уведомления');
  notifications.type = 'button';
  notifications.title = 'Разрешить уведомления, когда Messenger открыт';
  let socket = null, online = false, timer = null, timeoutMs = 1000, disposed = false;
  let call = null, pc = null, media = null, pendingIce = [], callTimer = null;

  const send = data => {
    if (!socket || socket.readyState !== WebSocket.OPEN) return false;
    socket.send(JSON.stringify(data)); return true;
  };
  function stopTracks() {
    if (media) for (const t of media.getTracks()) t.stop();
    media = null;
    if (pc) { pc.onicecandidate = null; pc.ontrack = null; pc.close(); }
    pc = null; local.srcObject = remote.srcObject = null;
    pendingIce = [];
  }
  function cleanupCall() {
    if (callTimer) clearTimeout(callTimer);
    callTimer = null;
    call = null; stopTracks();
    panel.classList.add('hidden'); mediaBox.classList.add('hidden');
  }
  const callPayload = type => call ? { type, call_id: call.id } : null;
  function endCall() {
    if (call) send(callPayload(call.direction === 'incoming' && call.status === 'incoming' ? 'call.decline' : 'call.end'));
    cleanupCall();
  }
  decline.addEventListener('click', endCall);
  hang.addEventListener('click', endCall);

  function renderCall() {
    if (!call) { panel.classList.add('hidden'); return; }
    panel.classList.remove('hidden');
    mediaBox.classList.toggle('hidden', call.status !== 'active');
    accept.classList.toggle('hidden', call.status !== 'incoming');
    decline.classList.toggle('hidden', call.status !== 'incoming');
    hang.classList.toggle('hidden', call.status === 'incoming');
    const mode = call.media === 'video' ? 'Видеозвонок' : 'Голосовой звонок';
    label.textContent = `${mode} · ${call.name} · ${
      call.status === 'incoming' ? 'Входящий' : call.status === 'ringing' ? 'Ожидание ответа' : 'Соединение'}`;
  }
  function expiry() {
    if (callTimer) clearTimeout(callTimer);
    callTimer = setTimeout(() => {
      if (call && call.status !== 'active') { endCall(); toast('Нет ответа на звонок'); }
    }, 65000);
  }
  async function prepareMedia() {
    if (!call || !navigator.mediaDevices?.getUserMedia || !window.RTCPeerConnection) {
      throw new Error('Звонки не поддерживаются в этом браузере');
    }
    const constraints = { audio: true, video: call.media === 'video' };
    media = await navigator.mediaDevices.getUserMedia(constraints);
    if (!call) { stopTracks(); return; }
    pc = new RTCPeerConnection({ iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] });
    pc.onicecandidate = event => {
      if (event.candidate && call) send({ ...callPayload('call.signal'), signal: { type: 'candidate', candidate: event.candidate.toJSON() } });
    };
    pc.ontrack = event => { remote.srcObject = event.streams[0] || new MediaStream([event.track]);
      remote.play().catch(() => { toast('Нажмите на видео, чтобы включить звук'); }); };
    pc.onconnectionstatechange = () => {
      if (!pc || !call) return;
      if (pc.connectionState === 'failed') { toast('Не удалось установить соединение. Возможно, нужен TURN-сервер.'); endCall(); }
      if (pc.connectionState === 'connected') { label.textContent = (call.media === 'video' ? 'Видеозвонок' : 'Звонок') + ' · Соединено'; }
    };
    media.getTracks().forEach(t => pc.addTrack(t, media));
    local.srcObject = media;
    local.play().catch(() => {});
  }
  async function offer() {
    await prepareMedia();
    if (!call || !pc) return;
    const description = await pc.createOffer();
    await pc.setLocalDescription(description);
    send({ ...callPayload('call.signal'), signal: { type: 'offer', sdp: pc.localDescription.sdp } });
  }
  async function receiveSignal(signal) {
    if (!call || !pc) return;
    if (signal.type === 'candidate') {
      if (!signal.candidate || typeof signal.candidate.candidate !== 'string') return;
      if (pc.remoteDescription) await pc.addIceCandidate(signal.candidate);
      else pendingIce.push(signal.candidate);
      return;
    }
    if (!['offer', 'answer'].includes(signal.type) || typeof signal.sdp !== 'string') return;
    await pc.setRemoteDescription({ type: signal.type, sdp: signal.sdp });
    for (const ice of pendingIce) await pc.addIceCandidate(ice);
    pendingIce = [];
    if (signal.type === 'offer') {
      const answer = await pc.createAnswer();
      await pc.setLocalDescription(answer);
      send({ ...callPayload('call.signal'), signal: { type: 'answer', sdp: pc.localDescription.sdp } });
    }
  }
  async function begin(mediaType) {
    const person = getContact();
    if (!person || person.kind === 'group') return toast('Звонки доступны только в личных чатах');
    if (!online) return toast('Нет связи с сервером звонков');
    if (call) return toast('Уже есть текущий звонок');
    call = { id: null, status: 'ringing', direction: 'outgoing', media: mediaType, name: person.display_name };
    renderCall(); expiry();
    if (!send({ type: 'call.invite', to: person.id, media: mediaType })) cleanupCall();
  }
  async function onEvent(e) {
    if (e.type === 'message.changed' || e.type === 'group.changed' || e.type === 'message.read') {
      if (active()) await onUpdate();
      const muted = chats().some(c => c.id === e.sender_id && c.muted);
      if (e.sender_id && e.sender_id !== state.user?.id && !muted && e.type !== 'message.read') {
        if (typeof Notification !== 'undefined' && Notification.permission === 'granted' && document.hidden) {
          try { new Notification('Vainah Messenger', { body: 'Новое сообщение · Откройте Vainah', tag: 'vainah-message' }); } catch {}
        } else if (document.visibilityState === 'visible' && e.type === 'message.changed') {
          toast('Новое сообщение в Vainah Messenger');
        }
      }
    } else if (e.type === 'call.ringing' && call?.status === 'ringing') {
      call.id = e.call_id;
      renderCall();
    } else if (e.type === 'call.incoming') {
      if (call) return;
      call = { id: e.call_id, status: 'incoming', direction: 'incoming', media: e.media,
        name: e.name || 'Vainah ID' };
      renderCall(); expiry();
    } else if (e.type === 'call.unavailable') {
      toast(e.reason || 'Абонент недоступен'); cleanupCall();
    } else if (e.type === 'call.accepted' && call?.id === e.call_id) {
      call.status = 'active';
      if (callTimer) clearTimeout(callTimer);
      renderCall();
      if (call.direction === 'outgoing') try { await offer(); }
      catch (error) { toast(error.message); endCall(); }
    } else if (e.type === 'call.signal' && call?.id === e.call_id) {
      try { await receiveSignal(e.signal); } catch (error) { toast('Ошибка соединения: ' + error.message); endCall(); }
    } else if (e.type === 'call.ended' && call?.id === e.call_id) {
      cleanupCall(); toast('Звонок завершён');
    } else if (e.type === 'error') {
      toast(e.message || 'Ошибка подключения');
    }
  }
  accept.addEventListener('click', async () => {
    if (!call || call.status !== 'incoming') return;
    accept.disabled = true;
    try {
      await prepareMedia();
      if (!call) return;
      call.status = 'active'; renderCall(); send(callPayload('call.accept'));
    } catch (e) { toast(e.message); endCall(); }
    finally { accept.disabled = false; }
  });
  notifications.addEventListener('click', async () => {
    if (!('Notification' in window) || !window.isSecureContext) return toast('Уведомления требуют HTTPS и совместимый браузер');
    const permission = await Notification.requestPermission();
    toast(permission === 'granted' ? 'Уведомления разрешены, пока Messenger открыт' : 'Уведомления не разрешены');
  });
  function connect() {
    if (disposed || !stage.isConnected || !state.user) return;
    const url = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/api/messenger/v2/live`;
    try { socket = new WebSocket(url); } catch { retry(); return; }
    socket.onopen = () => { online = true; timeoutMs = 1000; status.textContent = '● Онлайн';
      status.classList.add('connected'); };
    socket.onmessage = ev => { try { const data = JSON.parse(ev.data); Promise.resolve(onEvent(data)).catch(console.error); } catch {} };
    socket.onclose = () => {
      online = false; status.textContent = '○ Переподключение'; status.classList.remove('connected');
      if (call) cleanupCall(); retry();
    };
    socket.onerror = () => { /* onclose handles reconnect */ };
  }
  function retry() {
    if (disposed || !stage.isConnected) return;
    timer = setTimeout(connect, timeoutMs);
    timeoutMs = Math.min(timeoutMs * 2, 15000);
  }
  const cleanup = () => {
    if (disposed) return;
    disposed = true; observer.disconnect();
    if (timer) clearTimeout(timer);
    if (socket) { socket.onclose = null; socket.close(); }
    cleanupCall(); panel.remove();
  };
  const observer = new MutationObserver(() => { if (!stage.isConnected) cleanup(); });
  observer.observe(stage.parentElement, {childList: true});
  connect();
  return { status, notifications, callAudio: () => begin('audio'), callVideo: () => begin('video'),
    isOnline: () => online, dispose: cleanup };
}
