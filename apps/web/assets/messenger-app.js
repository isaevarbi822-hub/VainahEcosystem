import { mountStandaloneMessenger } from './suite-ui.js';

const $ = (id) => document.getElementById(id);
const state = { user:null, csrf:'', mode:'login', screen:'chats' };
let toastHandle;
function toast(message) {
  const el=$('vm-toast');el.textContent=message;el.classList.remove('hidden');
  clearTimeout(toastHandle);toastHandle=setTimeout(()=>el.classList.add('hidden'),4200);
}
async function api(url, options={}) {
  const method=(options.method||'GET').toUpperCase();
  const headers={...(options.headers||{})};
  let body=options.body;
  if(body && !(body instanceof FormData) && typeof body!=='string') {
    headers['Content-Type']='application/json';body=JSON.stringify(body);
  }
  if(state.csrf && !['GET','HEAD','OPTIONS'].includes(method))headers['X-CSRF-Token']=state.csrf;
  const response=await fetch(url,{method,headers,body,credentials:'same-origin'});
  let data;
  try {data=await response.json();}catch{data={};}
  if(!response.ok) {
    let detail=data.detail;
    if(Array.isArray(detail))detail=detail.map(x=>x.msg).join('; ');
    throw new Error(typeof detail==='string'?detail:`Ошибка сервера: ${response.status}`);
  }
  return data;
}
function showAuth(mode='login') {
  state.mode=mode;const register=mode==='register';
  $('auth-overlay').classList.remove('hidden');
  $('auth-heading').textContent=register?'Создать Vainah ID':'Войти в Vainah Messenger';
  $('auth-desc').textContent=register?'Создайте аккаунт, чтобы начать общаться.':'Войдите через email и пароль.';
  $('vm-name-label').classList.toggle('hidden',!register);
  // Public email registration is instant when VAINAH_SIGNUP_MODE=open.
  // Invitation mode remains available server-side for private previews.
  $('vm-invite-label').classList.add('hidden');
  $('vm-name').required=register;
  $('vm-password').autocomplete=register?'new-password':'current-password';
  $('vm-auth-submit').textContent=register?'Зарегистрироваться':'Войти';
  $('vm-switch-auth').textContent=register?'Уже есть аккаунт? Войти':'Нет аккаунта? Создать Vainah ID';
  $('vm-auth-error').classList.add('hidden');
  $('vm-email').focus();
}
function hideAuth() {$('auth-overlay').classList.add('hidden');}
async function startWorkspace() {
  $('marketing').classList.add('hidden');hideAuth();$('vm-workspace').classList.remove('hidden');
  $('vm-my-name').textContent=state.user.display_name;
  $('vm-my-avatar').textContent=(state.user.display_name||'V')[0].toUpperCase();
  $('vm-app-email').textContent=state.user.email;
  $('vm-profile-name').value=state.user.display_name;
  $('vm-my-id').textContent=state.user.id;
  await refreshVerified();
  await openSection('chats');
}
async function refreshVerified() {
  try {
    const d=await api('/api/messenger/v2/verification/me');
    $('vm-self-badge').classList.toggle('hidden',!d.verified);
    $('vm-verification-admin').classList.toggle('hidden',!d.can_manage);
  } catch { $('vm-self-badge').classList.add('hidden'); }
}
async function openSection(name) {
  state.screen=name;
  $('vm-workspace').classList.remove('vm-chat-open');
  $('vm-rail-chats').classList.toggle('active',name==='chats');
  $('vm-rail-settings').classList.toggle('active',name==='settings');
  $('vm-floating-compose').classList.toggle('hidden',name!=='chats');
  for(const id of ['vm-rail-channels','vm-rail-bots']){
    const el=$(id);if(el)el.classList.toggle('active',name===id.slice(8));
  }
  $('screen-feature').classList.toggle('hidden',name==='settings');
  $('vm-settings-panel').classList.toggle('hidden',name!=='settings');
  $('breadcrumb-name').textContent=({chats:'Vainah',channels:'Каналы',bots:'Боты',settings:'Настройки'})[name]||'Messenger';
  if(name==='chats'){
    await mountStandaloneMessenger($('feature-root'),{api,state,showToast:toast,openChannel,openBot});
  }else if(name==='channels' || name==='bots'){
    await openCommunity(name);
  }
}
async function openCommunity(section){
  const root=$('feature-root');root.replaceChildren();
  const heading=document.createElement('div');heading.className='vm-community-head';
  const title=document.createElement('h2');title.textContent=section==='channels'?'Мои каналы':'Мои боты';
  const subtitle=document.createElement('p');subtitle.textContent=section==='channels'?
    'Публикуйте обновления для подписчиков своего канала.':'Настройте простого бота, который отвечает на сообщения.';
  heading.append(title,subtitle);root.append(heading);
  const form=document.createElement('form');form.className='vm-community-form';
  const name=document.createElement('input');name.required=true;name.maxLength=80;name.placeholder=section==='channels'?'Название канала':'Название бота';
  const description=document.createElement('input');description.maxLength=300;description.placeholder='Короткое описание';
  const submit=document.createElement('button');submit.className='vm-button vm-primary';submit.textContent='Создать';form.append(name,description,submit);
  root.append(form);
  const list=document.createElement('div');list.className='vm-community-list';root.append(list);
  const refresh=async()=>{
    list.replaceChildren();
    const rows=await api(section==='channels'?'/api/community/channels':'/api/community/bots');
    for(const item of rows.items){
      const box=document.createElement('article');box.className='vm-community-item';
      const head=document.createElement('h3');head.textContent=item.name+(item.verified?' ✓':'');
      const info=document.createElement('p');info.textContent=item.description||'Без описания';box.append(head,info);
      if(section==='channels') {
        const follow=document.createElement('button');follow.className='vm-button vm-soft';
        follow.textContent=item.subscribed?'Отписаться':'Подписаться';follow.type='button';
        follow.onclick=async()=>{try{await api(`/api/community/channels/${item.id}/subscribe`,{method:item.subscribed?'DELETE':'POST'});await refresh();}catch(e){toast(e.message);}};
        box.append(follow);
        const open=document.createElement('button');open.className='vm-button vm-outline';open.type='button';open.textContent='Публикации';
        open.onclick=()=>openChannel(item);box.append(open);
      }else if(item.owner){
        const open=document.createElement('button');open.className='vm-button vm-outline';open.type='button';open.textContent='Настроить ответы';
        open.onclick=()=>openBot(item);box.append(open);
      }
      list.append(box);
    }
    if(!rows.items.length){const empty=document.createElement('p');empty.textContent='Пока ничего нет. Создайте первым.';list.append(empty);}
  };
  form.onsubmit=async event=>{
    event.preventDefault();
    try{await api(section==='channels'?'/api/community/channels':'/api/community/bots',{method:'POST',body:{name:name.value,description:description.value}});
      form.reset();await refresh();toast('Создано');}catch(e){toast(e.message);}
  };
  try{await refresh();}catch(e){toast(e.message);}
}
async function openChannel(item) {
  const root=$('feature-root');root.replaceChildren();
  const back=document.createElement('button');back.className='vm-button vm-soft';back.textContent='← Все каналы';back.onclick=()=>openCommunity('channels');
  const title=document.createElement('h2');title.textContent=item.name;root.append(back,title);
  const entries=document.createElement('div');entries.className='vm-community-list';root.append(entries);
  if(item.owner){
    const form=document.createElement('form');form.className='vm-community-form';
    const input=document.createElement('textarea');input.maxLength=4000;input.required=true;input.placeholder='Новая публикация';
    const send=document.createElement('button');send.textContent='Опубликовать';send.className='vm-button vm-primary';
    form.append(input,send);root.append(form);
    form.onsubmit=async e=>{e.preventDefault();try{await api(`/api/community/channels/${item.id}/posts`,{method:'POST',body:{body:input.value}});input.value='';await refresh();}catch(err){toast(err.message);}};
  }
  async function refresh(){
    entries.replaceChildren();
    const rows=await api(`/api/community/channels/${item.id}/posts`);
    for(const post of rows.items){const article=document.createElement('article');article.className='vm-community-item';
      const body=document.createElement('p');body.textContent=post.body;article.append(body);entries.append(article);}
  }
  try{await refresh();}catch(e){toast(e.message);}
}
async function openBot(item) {
  const root=$('feature-root');root.replaceChildren();
  const back=document.createElement('button');back.className='vm-button vm-soft';back.textContent='← Все боты';back.onclick=()=>openCommunity('bots');
  const title=document.createElement('h2');title.textContent=item.name;root.append(back,title);
  if(item.owner){
  const form=document.createElement('form');form.className='vm-community-form';
  const trigger=document.createElement('input');trigger.placeholder='Ключевое слово';trigger.required=true;trigger.maxLength=80;
  const reply=document.createElement('textarea');reply.placeholder='Автоматический ответ';reply.required=true;reply.maxLength=1000;
  const button=document.createElement('button');button.className='vm-button vm-primary';button.textContent='Сохранить ответ';
  form.append(trigger,reply,button);root.append(form);
  form.onsubmit=async e=>{e.preventDefault();try{await api(`/api/community/bots/${item.id}/rules`,{method:'POST',body:{trigger:trigger.value,reply:reply.value}});form.reset();toast('Ответ добавлен');}catch(err){toast(err.message);}};
  }
  const testForm=document.createElement('form');testForm.className='vm-community-form';
  const prompt=document.createElement('input');prompt.placeholder='Напишите боту тестовое сообщение';prompt.maxLength=500;prompt.required=true;
  const testButton=document.createElement('button');testButton.className='vm-button vm-soft';testButton.textContent='Проверить бота';
  const answer=document.createElement('p');answer.className='vm-bot-answer';answer.setAttribute('role','status');
  testForm.append(prompt,testButton);root.append(testForm,answer);
  testForm.onsubmit=async e=>{
    e.preventDefault();
    try{const result=await api(`/api/community/bots/${item.id}/reply`,{method:'POST',body:{message:prompt.value}});
      answer.textContent=result.reply;
    }catch(err){answer.textContent=err.message;}
  };
}
async function restore(){
  try{const data=await api('/api/auth/me');state.user=data.user;state.csrf=data.csrf_token;await startWorkspace();}
  catch { $('marketing').classList.remove('hidden'); }
}
document.querySelectorAll('[data-auth]').forEach(button=>button.addEventListener('click',()=>showAuth(button.dataset.auth)));
$('auth-close').addEventListener('click',hideAuth);
$('auth-overlay').addEventListener('click',event=>{if(event.target===$('auth-overlay'))hideAuth();});
$('vm-switch-auth').addEventListener('click',()=>showAuth(state.mode==='login'?'register':'login'));
$('vm-auth-form').addEventListener('submit',async event=>{
  event.preventDefault();$('vm-auth-error').classList.add('hidden');
  const signup=state.mode==='register';
  const body={email:$('vm-email').value.trim(),password:$('vm-password').value};
  if(signup){body.display_name=$('vm-name').value.trim();body.invite_code=$('vm-invite').value.trim()||null;}
  try{
    const result=await api(signup?'/api/auth/register':'/api/auth/login',{method:'POST',body});
    state.user=result.user;state.csrf=result.csrf_token;
    $('vm-auth-form').reset();await startWorkspace();
  }catch(e){$('vm-auth-error').textContent=e.message;$('vm-auth-error').classList.remove('hidden');}
});
$('vm-rail-chats').addEventListener('click',()=>openSection('chats'));
$('vm-rail-settings').addEventListener('click',()=>openSection('settings'));
function openCompose() {
  if(state.screen!=='chats')openSection('chats').then(openCompose).catch(e=>toast(e.message));
  else {
    const sidebar=document.querySelector('.vchat-sidebar');
    sidebar?.classList.toggle('new-open');
    const field=document.querySelector('.vchat-new input');
    if(sidebar?.classList.contains('new-open'))field?.focus();
  }
}
$('vm-compose-action').addEventListener('click',openCompose);
$('vm-floating-compose').addEventListener('click',openCompose);
$('vm-search-action').addEventListener('click',()=>{
  if(state.screen!=='chats')openSection('chats').then(()=>document.querySelector('.vchat-sidebar input[type=search]')?.focus());
  else document.querySelector('.vchat-sidebar input[type=search]')?.focus();
});
for(const id of ['vm-rail-channels','vm-rail-bots']){const el=$(id);if(el)el.addEventListener('click',()=>openSection(id.slice(8)));}
$('vm-logout').addEventListener('click',async()=>{
  try{await api('/api/auth/logout',{method:'POST'});}catch(e){toast(e.message);return;}
  state.user=null;state.csrf='';$('vm-workspace').classList.add('hidden');
  $('vm-workspace').classList.remove('vm-chat-open');
  $('marketing').classList.remove('hidden');
});
$('vm-profile-form').addEventListener('submit',async e=>{
  e.preventDefault();
  try{const result=await api('/api/auth/profile',{method:'PATCH',body:{display_name:$('vm-profile-name').value}});
    state.user=result.user;$('vm-my-name').textContent=result.user.display_name;toast('Имя обновлено');}
  catch(err){toast(err.message);}
});
$('vm-copy-id').addEventListener('click',()=>{navigator.clipboard?.writeText(state.user.id).then(()=>toast('Vainah ID скопирован')).catch(()=>toast('Скопируйте ID вручную'));});
$('vm-verify-form').addEventListener('submit',async e=>{
  e.preventDefault();
  try{await api('/api/messenger/v2/verification/manage',{method:'POST',body:{user_id:$('vm-verify-target').value,verified:$('vm-verify-enabled').checked}});
    toast('Статус обновлён');await refreshVerified();}catch(err){toast(err.message);}
});
restore();
