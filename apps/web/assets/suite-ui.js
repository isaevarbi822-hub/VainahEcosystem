/* Vainah integrated app suite, no third-party scripts or unsanitized HTML.
 * All user-supplied content is rendered via textContent/value.
 */
const appLabels = {
  ai: ['✦', 'Vainah AI', 'Внешняя ИИ-модель подключается владельцем сервера'],
  messenger: ['◉', 'Vainah Messenger', 'Личные сообщения между аккаунтами Vainah ID'],
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
  const panel=section(); heading(panel,'Сообщения','Чтобы написать другому человеку, введите его точный email Vainah ID. Переписка хранится на вашем сервере; сквозное шифрование пока отсутствует.');
  const contactField=textInput('email@example.com',{type:'email',max:254});
  const contactBar=E('div','suite-inline');
  const contactList=E('div','suite-list');
  const threadView=E('div','suite-chat');
  const message=textInput('Ваше сообщение...',{multiline:true,max:3000});
  const send=btn('Отправить', async()=>{if(!chosen){toast('Выберите собеседника');return;}try{await api('/api/messenger/send',{method:'POST',body:{email:chosen.email,body:message.value}});message.value='';await loadThread();await loadContacts();}catch(err){errorHandler(err);}},'primary');
  let chosen=null, pollTimer=null;
  async function loadThread(){
    if(!chosen)return;
    const {items}=await api(`/api/messenger/thread/${chosen.id}`);
    collectRows(items,threadView,i=>E('div',`suite-bubble ${i.mine?'mine':''}`,i.body));
    threadView.scrollTop=threadView.scrollHeight;
  }
  async function select(c){ chosen=c; label.textContent='Переписка: '+c.display_name; await loadThread(); }
  async function loadContacts(){
    const {items}=await api('/api/messenger/contacts');
    collectRows(items,contactList,i=>btn(i.display_name+' · '+i.email,()=>select(i),'suite-contact'));
  }
  const label=E('h3','','Выберите собеседника');
  add(contactBar,contactField,btn('Найти',async()=>{try{const {contact}=await api('/api/messenger/contact?email='+encodeURIComponent(contactField.value));await select(contact);}catch(err){errorHandler(err);}}));
  add(panel,contactBar,E('h3','','Недавние контакты'),contactList,label,threadView,E('div','suite-inline'),message,send);
  root.append(panel); await loadContacts();
  const loop=async()=>{if(!document.getElementById('screen-feature').classList.contains('hidden') && state.user && document.getElementById('breadcrumb-name').textContent.endsWith('messenger')){
    try{await loadThread();}catch{} pollTimer=setTimeout(loop,5000);
  }};
  pollTimer=setTimeout(loop,5000);
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
