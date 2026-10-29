import { createMessengerRealtime } from "./messenger-live.js";
/* Vainah integrated app suite, no third-party scripts or unsanitized HTML.
 * All user-supplied content is rendered via textContent/value.
 */
const appLabels = {
  ai: ['✦', 'Vainah AI', 'Внешняя ИИ-модель подключается владельцем сервера'],
  messenger: ['◉', 'Vainah Messenger', 'Личные переписки, группы и голосовые сообщения в едином Vainah ID'],
  browser: ['◎', 'Vainah Browser', 'Закладки и открытие сайтов в системном браузере'],
  music: ['♫', 'Vainah Music', 'Личная медиатека собственных аудиофайлов'],
  weather: ['☁', 'Vainah Weather', 'Прогноз с Open-Meteo'],
  maps: ['⌖', 'Vainah Maps', 'Карта и любимые места'],
  translate: ['文', 'Vainah Translate', 'Перевод текста через MyMemory'],
  study: ['▣', 'Vainah Study', 'Учебные задания по предметам'],
  photos: ['▧', 'Vainah Photos', 'Приватная галерея'],
  calendar: ['▦', 'Vainah Calendar', 'Ваши события и расписание']
};
let api, state, toast;
const E = (tag, className, text) => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
};
function add(parent, ...children) { parent.append(...children); return parent; }
function btn(label, callback, cls='secondary-btn') {
  const b = E('button', cls, label); b.type = 'button'; b.addEventListener('click', callback); return b;
}
function textInput(placeholder, opts = {}) {
  const el = E(opts.multiline ? 'textarea' : 'input', 'suite-input');
  el.placeholder = placeholder; if (opts.type && !opts.multiline) el.type = opts.type;
  if (opts.value !== undefined) el.value = opts.value;
  if (opts.max) el.maxLength = opts.max;
  if (opts.required) el.required = true;
  return el;
}
function field(label, input) { const box = E('label', 'suite-field'); add(box, E('span', '', label), input); return box; }
function section() { return E('div', 'suite-panel'); }
function empty(text) { return E('p', 'suite-empty', text); }
function heading(parent, text, details) { add(parent, E('h2', 'suite-title', text), E('p', 'suite-help', details)); }
function errorHandler(err) { toast(err?.message || 'Ошибка запроса'); }
function collectRows(items, destination, make) {
  destination.replaceChildren(); if (!items.length) destination.append(empty('Пока ничего нет. Добавьте первую запись.'));
  for (const i of items) destination.append(make(i));
}
function safeHttp(url) {
  try { const u = new URL(url); return ['https:','http:'].includes(u.protocol) ? u.href : null; } catch { return null; }
}
function openExternal(url) { const safe = safeHttp(url); if (!safe) return; if (/Android/i.test(navigator.userAgent)) window.location.assign(safe); else window.open(safe, '_blank', 'noopener,noreferrer'); }
function shell(name) {
  const root = document.getElementById('feature-root'); root.replaceChildren();
  const [icon, title, subtitle] = appLabels[name];
  const header = E('div', 'page-header'); add(header, E('p', 'eyebrow', 'VAINAH APP · ' + icon), E('h1', '', title), E('p', '', subtitle));
  const launch = btn('Открыть отдельное приложение ↗', () => { window.location.assign('/app/' + name); });
  launch.title = 'Отдельная версия с собственным PWA-манифестом. Для установки используйте меню браузера на HTTPS.';
  header.append(launch);
  root.append(header); return root;
}
export function bootApps({ navigate }) {
  const nav = document.querySelector('.sidebar-nav');
  for (const [name, label] of Object.entries(appLabels)) {
    const item = E('button', 'nav-item'); item.type = 'button'; item.dataset.screen = name;
    add(item, E('span', 'nav-icon', label[0]), document.createTextNode(label[1]));
    nav.append(item); // app.js attaches navigation events to all data-screen buttons
  }
}
export async function showApp(name, context) {
  if (!appLabels[name]) return;
  ({ api, state, showToast: toast } = context);
  const root = shell(name);
  try {
    if (name === 'messenger') await messenger(root);
    else if (name === 'ai') await aiPanel(root);
    else if (name === 'weather') weatherPanel(root);
    else if (name === 'translate') translatePanel(root);
    else if (name === 'maps') await mapsPanel(root);
    else if (name === 'music' || name === 'photos') await mediaPanel(root, name === 'music' ? 'audio' : 'photo');
    else if (['calendar','study','browser'].includes(name)) await recordsPanel(root, name === 'browser' ? 'bookmarks' : name);
  } catch (err) { root.append(empty('Не удалось загрузить приложение: ' + err.message)); }
}
const specifications = {
  calendar: { fields: [['title','Название','text'],['date','Дата','date'],['time','Время','time'],['description','Описание','textarea']], caption: 'Календарь с личными событиями' },
  study: { fields: [['title','Задание','text'],['subject','Предмет','text'],['due','Срок','date'],['details','Детали','textarea']], caption: 'Запланируйте домашние задания и отмечайте выполнение' },
  bookmarks: { fields: [['title','Название','text'],['url','Ссылка','url']], caption: 'Открытие сайтов выполняется в системном браузере — без встроенного движка' }
};
async function recordsPanel(root, kind) {
  const spec = specifications[kind], panel = section(); heading(panel, 'Мои записи', spec.caption);
  const form = E('form', 'suite-form'), fields = {};
  for (const [key,label,type] of spec.fields) {
    const inp = textInput(label, { type, multiline:type==='textarea', max: type==='textarea' ? 2000 : 150 });
    fields[key] = inp; form.append(field(label, inp));
  }
  if (kind === 'study') { const box = E('label','suite-checkbox'); const c = E('input'); c.type='checkbox'; fields.done=c; add(box,c,E('span','','Выполнено')); form.append(box); }
  const submit = E('button','primary','Добавить'); submit.type='submit'; form.append(submit);
  const list = E('div','suite-list'); let editingId = null;
  form.addEventListener('submit', async e => {
    e.preventDefault();
    const payload = Object.fromEntries(Object.entries(fields).map(([k,v])=>[k,v.type==='checkbox' ? v.checked : v.value]));
    try {
      await api(editingId ? `/api/data/${kind}/${editingId}` : `/api/data/${kind}`, {method: editingId?'PUT':'POST',body:{payload}});
      editingId = null; form.reset(); submit.textContent = 'Добавить'; await refresh(); toast('Сохранено');
    } catch(err) { errorHandler(err); }
  });
  async function refresh() {
    const {items} = await api(`/api/data/${kind}`);
    collectRows(items, list, item => {
      const p=item.payload, row=E('div','suite-row');
      const title=E('strong','',p.title || 'Без названия');
      const detail=E('span','suite-help', kind==='calendar'?`${p.date || 'Без даты'} ${p.time || ''} · ${p.description||''}`:
                      kind==='study'?`${p.subject || 'Без предмета'} · ${p.due || 'Без срока'} · ${p.done?'✓ Выполнено':'Не выполнено'}`:p.url);
      const box=E('div','suite-row-text'); add(box,title,detail);
      const buttons=E('div','suite-actions');
      if (kind==='bookmarks') buttons.append(btn('Открыть ↗',()=>openExternal(p.url)));
      buttons.append(btn('Изменить',()=>{editingId=item.id; for(const [k,v] of Object.entries(fields)) {if(v.type==='checkbox')v.checked=!!p[k];else v.value=p[k]||'';} submit.textContent='Сохранить изменения'; form.scrollIntoView({behavior:'smooth',block:'nearest'});}));
      buttons.append(btn('Удалить',async()=>{if(!confirm('Удалить запись?'))return;try{await api(`/api/data/${kind}/${item.id}`,{method:'DELETE'});await refresh();}catch(err){errorHandler(err);}},'danger-button'));
      return add(row,box,buttons);
    });
  }
  add(panel,form,E('h3','','Сохранённые записи'),list); root.append(panel); await refresh();
}
async function messenger(root) {
  const stage = E('div','vchat');
  const sidebar = E('aside','vchat-sidebar');
  const intro = E('div','vchat-side-top');
  add(intro, E('div','vchat-eyebrow','VAINAH · ЛИЧНОЕ ОБЩЕНИЕ'), E('h2','','Сообщения'));
  const search = textInput('Поиск чатов по имени или email', {max:254});
  search.type='search'; search.setAttribute('aria-label','Поиск переписок');
  const find = E('form','vchat-new');
  const email = textInput('Email Vainah ID',{type:'email',max:254}); email.required=true;
  const findButton=E('button','primary','Новый чат'); findButton.type='submit';
  add(find,email,findButton);
  const filters=E('div','vchat-filters');
  const filterButtons={};
  for(const [key,label] of Object.entries({all:'Все',unread:'Непрочитанные',groups:'Группы',archived:'Архив'})){
    filterButtons[key]=btn(label,()=>{activeFilter=key;renderChats();},'vchat-filter');
    filters.append(filterButtons[key]);
  }
  const groupDetails=E('details','vchat-group-create');
  const groupSummary=E('summary','','＋ Создать группу');
  const groupForm=E('form','vchat-group-form');
  const groupName=textInput('Название группы',{max:80});groupName.required=true;
  const groupEmails=textInput('Email участников через запятую',{max:1500});
  const groupSubmit=E('button','primary','Создать группу');groupSubmit.type='submit';
  add(groupForm,groupName,groupEmails,groupSubmit);
  add(groupDetails,groupSummary,groupForm);
  const contacts = E('div','vchat-contacts');
  add(sidebar,intro,search,find,groupDetails,filters,contacts);

  const area=E('section','vchat-area');
  const header=E('div','vchat-header');
  const back=btn('‹',()=>{}, 'vchat-back'); // Back button is wired below.
  const face=E('span','vchat-avatar','V');
  const name=E('strong','', 'Выберите чат');
  const presence=E('small','', 'История сообщений доступна только участникам');
  const identity=E('div','vchat-identity'); add(identity,name,presence);
  const headerLeft=E('div','vchat-person');add(headerLeft,back,face,identity);
  const controls=E('div','vchat-header-actions');
  const searchInChat=btn('⌕',()=>searchThread(),'vchat-soft');
  searchInChat.title='Найти сообщение в чате';searchInChat.disabled=true;
  const prefs=E('select','vchat-soft');prefs.setAttribute('aria-label','Действия с чатом');
  for(const [value,label] of Object.entries({'':'⋯ Чат',pin:'📌 Закрепить',archive:'🗂 Архивировать',mute:'🔕 Без звука',members:'👥 Участники',invite:'＋ Участник',leave:'Выйти из группы',remove:'Удалить группу'})){
    const opt=E('option','',label);opt.value=value;prefs.append(opt);
  }
  prefs.disabled=true;prefs.addEventListener('change',()=>{const what=prefs.value;prefs.value='';if(what)doChatAction(what);});
  const callAudio=btn('☎',()=>live.callAudio(),'vchat-soft');callAudio.title='Голосовой звонок (тестовая версия)';callAudio.disabled=true;
  const callVideo=btn('▣',()=>live.callVideo(),'vchat-soft');callVideo.title='Видеозвонок (тестовая версия)';callVideo.disabled=true;
  const blockBtn=btn('Заблокировать',()=>toggleBlock(),'vchat-soft');
  blockBtn.disabled=true;
  add(controls,callAudio,callVideo,searchInChat,prefs,blockBtn);
  add(header,headerLeft,controls);
  const info=E('p','vchat-disclaimer','Сообщения хранятся на сервере Vainah. Сквозного шифрования пока нет. Не отправляйте секреты.');
  const stream=E('div','vchat-stream'); stream.setAttribute('role','log');stream.setAttribute('aria-label','Сообщения');
  const replyBar=E('div','vchat-reply-bar hidden');
  const replyLabel=E('span','','Ответ на сообщение');
  const cancelReply=btn('✕',()=>{replyTarget=null;replyBar.classList.add('hidden');},'vchat-mini');
  add(replyBar,replyLabel,cancelReply);
  const composer=E('form','vchat-composer');
  const attach=E('input');attach.type='file';attach.className='hidden';
  attach.accept='image/png,image/jpeg,image/gif,image/webp,audio/mpeg,audio/wav,audio/ogg,audio/mp4';
  const attachBtn=btn('＋',()=>attach.click(),'vchat-attach');attachBtn.title='Отправить изображение или аудиофайл до 5 МБ';
  const input=textInput('Написать сообщение…',{multiline:true,max:3000}); input.rows=1;
  input.setAttribute('aria-label','Текст сообщения');
  const recordBtn=btn('🎙',()=>toggleRecording(),'vchat-attach');recordBtn.title='Записать голосовое сообщение';
  const sendBtn=E('button','vchat-send','➤');sendBtn.type='submit';sendBtn.title='Отправить';
  add(composer,attachBtn,recordBtn,input,sendBtn,attach);
  add(area,header,info,stream,replyBar,composer);
  add(stage,sidebar,area);
  root.append(stage);
  const status=E('p','vchat-footnote','Vainah Messenger · Ваши чаты. Ваш стиль.');root.append(status);
  let chosen=null, chats=[], groups=[], busy=false, polling=false, lastSignature='', activeFilter='all';
  let replyTarget=null, recorder=null, recordingStream=null, recordChunks=[];
  const isGroup=()=>chosen?.kind==='group';
  const active=()=>document.getElementById('feature-root').contains(stage)&&
    !document.getElementById('screen-feature').classList.contains('hidden')&&
    state.user && document.getElementById('breadcrumb-name').textContent === 'Vainah messenger';
  const timeText=t=>new Intl.DateTimeFormat('ru-RU',{hour:'2-digit',minute:'2-digit'}).format(new Date(t*1000));
  const myBubble=message=>{
    const row=E('div',`vchat-line ${message.mine?'own':''}`);
    const bubble=E('div',`vchat-bubble ${message.deleted?'removed':''}`);
    if(isGroup()&&!message.mine)bubble.append(E('strong','vchat-sender',message.sender || 'Участник'));
    if(message.reply_to && !message.deleted){
      bubble.append(E('div','vchat-quote', (message.reply_to.mine?'Вы: ':'')+message.reply_to.body));
    }
    if(message.deleted){bubble.append(E('i','','Сообщение удалено'));}
    else {
      if(message.body)bubble.append(E('div','vchat-body',message.body));
      if(message.attachment){
        const a=message.attachment;
        if(a.type.startsWith('image/')) {
          const img=E('img','vchat-image');img.src=a.url;img.alt=a.filename;img.loading='lazy';bubble.append(img);
        } else {const audio=E('audio','vchat-audio');audio.src=a.url;audio.controls=true;audio.preload='none';bubble.append(audio);}
        bubble.append(E('small','vchat-file-name',a.filename));
      }
      if(message.reactions.length){const reactions=E('div','vchat-reactions');
        for(const r of message.reactions)reactions.append(E('span',r.mine?'vchat-reaction mine':'vchat-reaction',r.emoji));
        bubble.append(reactions);
      }
    }
    const stamp=E('span','vchat-timestamp',timeText(message.created_at)+(message.edited_at?' · изм.':'')+
      (message.mine?(message.read_at?' · ✓✓ Прочитано':' · ✓ Отправлено'):''));
    bubble.append(stamp);
    if(!message.deleted){
      const actions=E('div','vchat-message-actions');
      if(!isGroup())actions.append(btn('↩ Ответить',()=>{
        replyTarget={id:message.id,body:message.body || 'Вложение'};
        replyLabel.textContent='↩ '+replyTarget.body.slice(0,110);
        replyBar.classList.remove('hidden');input.focus();
      },'vchat-mini'));
      const reactPick=E('select','vchat-reaction-picker');
      const defaultOpt=E('option','','♡ Реакция');defaultOpt.value='';reactPick.append(defaultOpt);
      for(const emoji of ['❤️','👍','😂','😮','😢','🔥']){const opt=E('option','',emoji);opt.value=emoji;reactPick.append(opt);}
      reactPick.setAttribute('aria-label','Добавить реакцию');
      reactPick.addEventListener('change', async()=>{
        if(!reactPick.value)return;
        try{await api('/api/messenger/v2/message/'+message.id+'/reaction',{method:'PUT',body:{emoji:reactPick.value}});await loadThread(true);}catch(e){errorHandler(e);}
      }); actions.append(reactPick);
      if(message.body){
        actions.append(btn('В Notes',async()=>{
          try{
            await api('/api/notes',{method:'POST',body:{title:'Из Vainah Messenger',content:message.body}});
            toast('Сообщение сохранено в Vainah Notes');
          }catch(err){errorHandler(err);}
        },'vchat-mini'));
      }
      if(message.mine && !isGroup()){
        if(!message.attachment && Math.floor(Date.now()/1000)-message.created_at<=900){
          actions.append(btn('Изменить',async()=>{
            const body=prompt('Изменить сообщение:',message.body);
            if(body===null||!body.trim())return;
            try{await api('/api/messenger/v2/message/'+message.id,{method:'PATCH',body:{body}});await loadThread(true);}catch(e){errorHandler(e);}
          },'vchat-mini'));
        }
        actions.append(btn('Удалить',async()=>{if(!confirm('Удалить сообщение для обоих участников?'))return;
          try{await api('/api/messenger/v2/message/'+message.id,{method:'DELETE'});await loadThread(true);await loadChats();}catch(e){errorHandler(e);}
        },'vchat-mini danger'));
      }else if(!isGroup()){
        actions.append(btn('Пожаловаться',async()=>{
          const reason=prompt('Причина жалобы (минимум 3 символа):');if(reason===null||reason.trim().length<3)return;
          try{const result=await api('/api/messenger/v2/report',{method:'POST',body:{message_id:message.id,reason}});toast(result.notice);}catch(e){errorHandler(e);}
        },'vchat-mini'));
      }
      bubble.append(actions);
    }
    row.append(bubble);return row;
  };
  function renderChats(){
    const q=search.value.trim().toLocaleLowerCase();contacts.replaceChildren();
    for(const [key,button] of Object.entries(filterButtons))button.classList.toggle('active',key===activeFilter);
    const direct=chats.map(c=>({...c,kind:'direct',name:c.display_name}));
    const allGroups=groups.map(g=>({...g,kind:'group',display_name:g.name,email:`${g.members} участников`,archived:false,pinned:false,muted:false}));
    let visible=[...direct,...allGroups].filter(c=>{
      if(activeFilter==='archived')return c.archived;
      if(c.archived)return false;
      if(activeFilter==='groups'&&c.kind!=='group')return false;
      if(activeFilter==='unread'&&!c.unread)return false;
      return true;
    });
    visible=visible.filter(c=>(c.display_name+' '+c.email).toLocaleLowerCase().includes(q));
    visible.sort((a,b)=>Number(!!b.pinned)-Number(!!a.pinned)||b.updated_at-a.updated_at);
    if(!visible.length)contacts.append(empty(q?'Ничего не найдено.':'Здесь пока нет чатов. Создайте группу или найдите контакт.'));
    for(const c of visible){
      const item=E('button',`vchat-contact ${chosen?.id===c.id&&chosen?.kind===c.kind?'active':''}`);item.type='button';
      const avatar=E('span','vchat-avatar',c.kind==='group'?'👥':c.display_name.slice(0,1).toUpperCase());
      const main=E('span','vchat-contact-main');
      add(main,E('strong','',(c.pinned?'📌 ':'')+c.display_name+(c.muted?' 🔕':'')),
        E('small','',c.blocked?'Контакт заблокирован':c.preview||c.email));
      add(item,avatar,main);
      if(c.unread)item.append(E('span','vchat-count',String(Math.min(c.unread,99))));
      item.addEventListener('click',()=>select(c));contacts.append(item);
    }
  }
  async function loadChats(){
    const [direct,team]=await Promise.all([api('/api/messenger/v2/chats'),api('/api/messenger/v2/groups')]);
    chats=direct.items;groups=team.items;renderChats();
  }
  async function loadThread(background=false){
    if(!chosen||busy)return;busy=true;
    try{
      const selectedId=chosen.id,groupMode=isGroup();
      const url=groupMode?`/api/messenger/v2/groups/${selectedId}/messages`:`/api/messenger/v2/thread/${selectedId}`;
      const data=await api(url);
      if(!chosen||chosen.id!==selectedId||isGroup()!==groupMode)return;
      const sig=JSON.stringify(data.items);
      if(!background||sig!==lastSignature){
        const nearBottom=stream.scrollHeight-stream.scrollTop-stream.clientHeight<140;
        stream.replaceChildren();
        if(!data.items.length)stream.append(E('div','vchat-welcome','Начните переписку. Ваше первое сообщение появится здесь.'));
        for(const item of data.items)stream.append(myBubble(item));
        if(!background||nearBottom)stream.scrollTop=stream.scrollHeight;
        lastSignature=sig;
      }
      const blocked=groupMode?false:data.blocked;
      blockBtn.textContent=blocked?'Разблокировать':'Заблокировать';
      input.disabled=sendBtn.disabled=blocked;
      attachBtn.disabled=groupMode||blocked;
      recordBtn.disabled=groupMode||blocked;
      input.placeholder=blocked?'Разблокируйте контакт, чтобы написать':'Написать сообщение…';
      if(document.visibilityState==='visible' && active()){
        if(groupMode){if(data.items.length){await api(`/api/messenger/v2/groups/${selectedId}/read`,{method:'POST'});await loadChats();}}
        else if(data.items.some(m=>!m.mine&&!m.read_at)){
          await api('/api/messenger/v2/thread/'+selectedId+'/read',{method:'POST'});await loadChats();
        }
      }
    }finally{busy=false;}
  }
  async function select(contact){
    chosen={...contact,kind:contact.kind||'direct'};contact=chosen;lastSignature='';replyTarget=null;replyBar.classList.add('hidden');
    name.textContent=contact.display_name;
    presence.textContent=contact.kind==='group'?`${contact.members} участников · переписка на сервере`:contact.email;
    face.textContent=contact.kind==='group'?'👥':contact.display_name.slice(0,1).toUpperCase();
    blockBtn.disabled=contact.kind==='group';blockBtn.classList.toggle('hidden',contact.kind==='group');
    searchInChat.disabled=false;prefs.disabled=false;callAudio.disabled=callVideo.disabled=contact.kind==='group'||!!contact.blocked;
    stage.classList.add('thread-open');renderChats();
    try{await loadThread();}catch(e){errorHandler(e);}
    input.focus();
  }
  async function searchThread(){
    if(!chosen)return;
    if(isGroup()){toast('Поиск по группам появится в следующем обновлении');return;}
    const query=prompt('Найти сообщение в переписке:');
    if(!query||query.trim().length<2)return;
    try{
      const data=await api(`/api/messenger/v2/search/${chosen.id}?q=${encodeURIComponent(query.trim())}`);
      if(!data.items.length)return toast('Совпадений не найдено');
      stream.replaceChildren(E('div','vchat-search-title',`Найдено: ${data.items.length}`));
      for(const message of data.items)stream.append(myBubble(message));
      toast('Чтобы вернуться к переписке, выберите чат ещё раз');
    }catch(err){errorHandler(err);}
  }
  async function doChatAction(action){
    if(!chosen)return;
    try{
      if(isGroup()){
        if(action==='members'){
          const details=await api(`/api/messenger/v2/groups/${chosen.id}`);
          toast('Участники: '+details.people.map(p=>p.display_name).join(', ').slice(0,180));
        }else if(action==='remove'){
          if(!confirm('Безвозвратно удалить группу и всю переписку для всех участников?'))return;
          await api(`/api/messenger/v2/groups/${chosen.id}`,{method:'DELETE'});
          chosen=null;stage.classList.remove('thread-open');await loadChats();toast('Группа удалена');
        }else if(action==='invite'){
          const email=prompt('Email пользователя Vainah ID:');if(!email)return;
          await api(`/api/messenger/v2/groups/${chosen.id}/invite`,{method:'POST',body:{email}});
          toast('Пользователь добавлен');await loadChats();
        }else if(action==='leave'){
          if(!confirm('Выйти из группы? Администратор должен удалить свою группу.'))return;
          await api(`/api/messenger/v2/groups/${chosen.id}/leave`,{method:'DELETE'});
          chosen=null;stage.classList.remove('thread-open');await loadChats();
        }else toast('Для группы это действие пока недоступно');
      }else if(['pin','archive','mute'].includes(action)){
        const key={pin:'pinned',archive:'archived',mute:'muted'}[action];
        const current=chats.find(c=>c.id===chosen.id);
        const patch={[key]:!current?.[key]};
        const updated=await api(`/api/messenger/v2/preferences/${chosen.id}`,{method:'PATCH',body:patch});
        chosen={...chosen,...updated};await loadChats();
        toast(updated[key]?'Настройка включена':'Настройка выключена');
      }
    }catch(err){errorHandler(err);}
  }
  groupForm.addEventListener('submit',async e=>{
    e.preventDefault();
    const emails=groupEmails.value.split(',').map(x=>x.trim()).filter(Boolean);
    try{
      const created=await api('/api/messenger/v2/groups',{method:'POST',body:{name:groupName.value,emails}});
      groupName.value='';groupEmails.value='';groupDetails.open=false;
      await loadChats();activeFilter='groups';renderChats();
      const group=groups.find(g=>g.id===created.id);if(group)await select({...group,kind:'group',display_name:group.name,email:''});
      toast('Группа создана');
    }catch(err){errorHandler(err);}
  });
  async function toggleRecording(){
    if(isGroup()||!chosen)return;
    if(recorder?.state==='recording'){recorder.stop();recordBtn.textContent='🎙';return;}
    if(!navigator.mediaDevices?.getUserMedia||typeof MediaRecorder==='undefined'){
      toast('Запись голоса не поддерживается. Можно отправить готовый аудиофайл.');return;
    }
    try{
      recordingStream=await navigator.mediaDevices.getUserMedia({audio:true});
      const type=['audio/webm;codecs=opus','audio/webm','audio/ogg'].find(t=>MediaRecorder.isTypeSupported(t));
      if(!type){recordingStream.getTracks().forEach(t=>t.stop());toast('Формат записи недоступен');return;}
      const recordFor=chosen.id;recordChunks=[];recorder=new MediaRecorder(recordingStream,{mimeType:type});
      recorder.ondataavailable=e=>{if(e.data?.size)recordChunks.push(e.data);};
      recorder.onstop=async()=>{
        recordingStream?.getTracks().forEach(t=>t.stop());recordBtn.textContent='🎙';
        const blob=new Blob(recordChunks,{type:type.split(';')[0]});
        if(!blob.size||blob.size>5*1024*1024){toast('Запись должна быть меньше 5 МБ');return;}
        const file=new File([blob],'Vainah-voice.'+(type.includes('webm')?'webm':'ogg'),{type:blob.type});
        if(!chosen || chosen.id!==recordFor || isGroup()){toast('Чат изменён: запись не отправлена');return;}
        await uploadAttachment(file);
      };
      recorder.start();recordBtn.textContent='■';toast('Запись началась. Нажмите ■, чтобы отправить.');
    }catch(err){recordingStream?.getTracks().forEach(t=>t.stop());errorHandler(err);}
  }
  async function uploadAttachment(file){
    if(!chosen||isGroup())return toast('Вложения доступны в личных чатах');
    if(file.size>5*1024*1024)return toast('Максимум 5 МБ');
    const form=new FormData();form.append('contact_id',chosen.id);form.append('file',file);
    attachBtn.disabled=true;
    try{
      const response=await fetch('/api/messenger/v2/send-file',{method:'POST',headers:{'X-CSRF-Token':state.csrf},body:form,credentials:'same-origin'});
      const obj=await response.json().catch(()=>({}));if(!response.ok)throw new Error(obj.detail||'Ошибка загрузки');
      await loadThread();await loadChats();toast('Файл отправлен');
    }catch(err){errorHandler(err);}finally{attachBtn.disabled=false;}
  }
  async function toggleBlock(){if(!chosen)return;
    const blocked=blockBtn.textContent==='Разблокировать';
    if(!blocked&&!confirm('Заблокировать контакт? Новые сообщения будут запрещены для обеих сторон.'))return;
    try{await api('/api/messenger/v2/block/'+chosen.id,{method:blocked?'DELETE':'PUT'});
      await loadChats();await loadThread();toast(blocked?'Контакт разблокирован':'Контакт заблокирован');
    }catch(e){errorHandler(e);}
  }
  back.addEventListener('click',()=>stage.classList.remove('thread-open'));
  search.addEventListener('input',renderChats);
  find.addEventListener('submit',async e=>{
    e.preventDefault();try{const {contact}=await api('/api/messenger/contact?email='+encodeURIComponent(email.value.trim()));
      await select(contact);email.value='';
    }catch(err){errorHandler(err);}
  });
  composer.addEventListener('submit',async e=>{
    e.preventDefault();if(!chosen||!input.value.trim()||sendBtn.disabled)return;
    sendBtn.disabled=true;const body=input.value;
    try{
      if(isGroup())await api(`/api/messenger/v2/groups/${chosen.id}/send`,{method:'POST',body:{body}});
      else await api('/api/messenger/v2/send',{method:'POST',body:{contact_id:chosen.id,body,
        ...(replyTarget?{reply_to_id:replyTarget.id}:{})}});
      input.value='';replyTarget=null;replyBar.classList.add('hidden');
      await loadThread();await loadChats();
    }catch(err){errorHandler(err);}
    finally{sendBtn.disabled=false;}
  });
  input.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();composer.requestSubmit();}});
  attach.addEventListener('change',async()=>{
    const file=attach.files?.[0];if(!file)return;
    await uploadAttachment(file);attach.value='';
  });
  const live=createMessengerRealtime({stage,state,active,getContact:()=>chosen,chats:()=>chats,
    onUpdate:async()=>{await loadChats();if(chosen)await loadThread(true);},toast});
  intro.append(live.status);controls.prepend(live.notifications);
  try{await loadChats();}catch(e){errorHandler(e);}
  const poll=async()=>{
    if(!stage.isConnected)return;
    if(active() && document.visibilityState==='visible' && !polling && !live.isOnline()){
      polling=true;try{await loadChats();if(chosen)await loadThread(true);}catch{}finally{polling=false;}
    }
    if(stage.isConnected)setTimeout(poll,4000);
  };
  setTimeout(poll,4000);
}
async function aiPanel(root) {
  const panel=section(); const {configured}=await api('/api/ai/status');
  heading(panel,configured?'Напишите свой вопрос':'Модель пока не подключена', configured?
    'Сообщения отправляются настроенному оператором ИИ-провайдеру. Не отправляйте пароли или секреты.':
    'Владелец сервера должен настроить ключ и модель в переменных окружения. Это реальный клиент API, не фальшивый чат-бот.');
  const prompt=textInput('Напишите вопрос для Vainah AI',{multiline:true,max:4000}), output=E('div','suite-answer','Ответ появится здесь');
  const ask=btn('Спросить ИИ',async()=>{output.textContent='Генерация ответа...';try{const {answer}=await api('/api/ai/chat',{method:'POST',body:{prompt:prompt.value}});output.textContent=answer;}catch(e){output.textContent=e.message;}},'primary');
  ask.disabled=!configured; add(panel,prompt,ask,output);root.append(panel);
}
function locationSearch(onSelect, label='Введите город') {
  const form=E('form','suite-inline');
  const city=textInput(label,{max:80});city.required=true;
  const results=E('div','suite-list'); const button=E('button','primary','Найти');button.type='submit';
  form.addEventListener('submit', async e=>{e.preventDefault();results.replaceChildren(empty('Поиск города...'));
    try {const data=await api('/api/location/search?city='+encodeURIComponent(city.value));
      collectRows(data.items,results,c=>btn(`${c.name}, ${c.country}`,()=>{results.replaceChildren();onSelect(c);},'suite-contact'));
    } catch(err) {results.replaceChildren(empty(err.message));}
  });
  add(form,city,button);return {form,results};
}
function weatherPanel(root){
  const panel=section();heading(panel,'Прогноз погоды','Введите город. Данные Open-Meteo могут быть недоступны без интернета.');
  const info=E('div','suite-weather');
  const lookup=locationSearch(async c=>{info.textContent='Загрузка прогноза...';try{
    const result=await api(`/api/weather?latitude=${c.latitude}&longitude=${c.longitude}`);
    const current=result.current, days=result.daily;
    info.replaceChildren(E('h2','',`${c.name}: ${current.temperature_2m} °C`),
      E('p','',`Ощущается как ${current.apparent_temperature} °C · Влажность ${current.relative_humidity_2m}% · Ветер ${current.wind_speed_10m} км/ч`));
    days.time?.forEach((day,i)=>info.append(E('div','suite-row',`${day}: ${days.temperature_2m_min[i]}…${days.temperature_2m_max[i]} °C · Осадки ${days.precipitation_probability_max[i]}%`)));
  } catch(err){info.textContent=err.message;}});
  add(panel,lookup.form,lookup.results,info,E('p','suite-help','Источник: Open-Meteo.com (данные могут обновляться с задержкой).'));root.append(panel);
}
function translatePanel(root){
  const panel=section(); heading(panel,'Переводчик','Текст будет передан внешнему сервису MyMemory по вашему нажатию кнопки. Не вставляйте личные и секретные данные.');
  const choose=E('div','suite-inline');
  const langs={ru:'Русский',en:'English',no:'Norsk',tr:'Türkçe',de:'Deutsch',fr:'Français',es:'Español',it:'Italiano',ar:'العربية',uk:'Українська'};
  function select(defaultValue){const el=E('select','suite-input');for(const [k,v] of Object.entries(langs)){const opt=E('option','',v);opt.value=k;el.append(opt);}el.value=defaultValue;return el;}
  const src=select('ru'),dst=select('en'),input=textInput('Введите текст (до 450 символов)',{multiline:true,max:450}),out=E('div','suite-answer','Перевод появится здесь');
  add(choose,field('Исходный язык',src),field('Язык перевода',dst));
  add(panel,choose,input,btn('Перевести',async()=>{out.textContent='Переводим...';try{const result=await api('/api/translate',{method:'POST',body:{text:input.value,source:src.value,target:dst.value}});out.textContent=result.translation;}catch(err){out.textContent=err.message;}},'primary'),out);
  root.append(panel);
}
async function mapsPanel(root){
  const panel=section();heading(panel,'Мои места','Поиск городов от Open-Meteo и карта OpenStreetMap. Места сохраняются в Vainah ID.');
  const frame=E('iframe','suite-map');frame.title='Карта OpenStreetMap';frame.loading='lazy';frame.referrerPolicy='no-referrer';
  const list=E('div','suite-list');
  function display(c){const lat=Number(c.latitude),lon=Number(c.longitude),span=.08;
    frame.src=`https://www.openstreetmap.org/export/embed.html?bbox=${lon-span}%2C${lat-span}%2C${lon+span}%2C${lat+span}&layer=mapnik&marker=${lat}%2C${lon}`;
    selected=c;
  }
  let selected=null;
  const save=btn('Сохранить место',async()=>{if(!selected)return toast('Найдите место');try{await api('/api/data/places',{method:'POST',body:{payload:{name:selected.name,latitude:selected.latitude,longitude:selected.longitude}}});await refresh();toast('Место сохранено');}catch(err){errorHandler(err);}},'primary');
  const lookup=locationSearch(display);
  async function refresh(){const {items}=await api('/api/data/places');collectRows(items,list,i=>{
    const row=E('div','suite-row');const actions=E('div','suite-actions');
    add(actions,btn('На карте',()=>display(i.payload)),btn('Удалить',async()=>{await api('/api/data/places/'+i.id,{method:'DELETE'});await refresh();},'danger-button'));
    return add(row,E('strong','',i.payload.name),actions);
  });}
  display({name:'Oslo',latitude:59.9139,longitude:10.7522});
  add(panel,lookup.form,lookup.results,save,frame,E('p','suite-help','© OpenStreetMap contributors'),E('h3','','Избранные места'),list);
  root.append(panel);await refresh();
}
async function mediaPanel(root, category){
  const panel=section(),isPhoto=category==='photo';
  heading(panel,isPhoto?'Мои фотографии':'Моя музыка',isPhoto?
    'Добавляйте PNG, JPG, GIF или WebP до 8 МБ. Галерея приватная и хранится на сервере.':
    'Загрузите собственный MP3, WAV, OGG или M4A до 20 МБ. Не загружайте музыку без права её хранить.');
  const upload=E('input','suite-input');upload.type='file';upload.accept=isPhoto?'image/png,image/jpeg,image/gif,image/webp':'audio/mpeg,audio/wav,audio/ogg,audio/mp4';
  const files=E('div',isPhoto?'suite-photos':'suite-list');
  async function refresh(){const {items}=await api(`/api/media/${category}`);collectRows(items,files,item=>{
    const card=E('div',isPhoto?'suite-photo-card':'suite-row');
    const controls=E('div','suite-actions');
    const display=isPhoto?E('img','suite-photo'):E('audio','suite-audio');
    display.src=item.url;
    if(isPhoto){display.alt=item.filename;display.loading='lazy';}else{display.controls=true;display.preload='none';}
    add(controls,btn('Удалить',async()=>{if(!confirm('Удалить файл?'))return;try{await api('/api/media/file/'+item.id,{method:'DELETE'});await refresh();}catch(e){errorHandler(e);}},'danger-button'));
    return add(card,display,E('span','suite-help',item.filename),controls);
  });}
  const action=btn('Загрузить',async()=>{const file=upload.files[0];if(!file)return toast('Выберите файл');
    const max=isPhoto?8*1024*1024:20*1024*1024;if(file.size>max)return toast('Файл превышает лимит');
    const body=new FormData();body.append('file',file);
    try{const response=await fetch(`/api/media/${category}`,{method:'POST',headers:{'X-CSRF-Token':state.csrf},body,credentials:'same-origin'});
      const obj=await response.json();if(!response.ok)throw new Error(typeof obj.detail==='string'?obj.detail:'Ошибка загрузки');upload.value='';await refresh();toast('Файл загружен');
    }catch(err){errorHandler(err);}},'primary');
  add(panel,upload,action,files);root.append(panel);await refresh();
}
