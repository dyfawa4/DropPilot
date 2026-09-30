// Exercise the real frontend with isolated sample data, never a Twitch account.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
let JSDOM;
try{({JSDOM}=require('jsdom'))}catch{({JSDOM}=require('../.qa-js/node_modules/jsdom'))}
const base=path.resolve(__dirname,'..');
const packs=JSON.parse(fs.readFileSync(path.join(base,'web/locales.json'),'utf8'));
function frontend(){
 const dom=new JSDOM(fs.readFileSync(path.join(base,'web/index.html'),'utf8'),{url:'http://localhost/?demo=1',runScripts:'outside-only',pretendToBeVisual:true});
 dom.window.scrollTo=()=>{};
 dom.window.navigator.clipboard={writeText:async()=>{}};
 const context=dom.getInternalVMContext();
 for(const file of ['locales.js','i18n.js','app.js'])vm.runInContext(fs.readFileSync(path.join(base,'web',file),'utf8'),context,{filename:file});
 return {dom,document:dom.window.document,run:code=>vm.runInContext(code,context)};
}
const tick=()=>new Promise(resolve=>setImmediate(resolve));
async function click(document,selector){const button=document.querySelector(selector);assert.ok(button,selector);button.click();await tick()}
function untranslated(document){
 const walker=document.createTreeWalker(document.body,4);let node,found=[];
 while(node=walker.nextNode())if(!node.parentElement.closest('[data-i18n-skip],.campaign-game,.campaign-name,.hero-game,.hero-title,.hero-info,.queue-game,.game-result>span,.channel-identity b,.login-code,.reward-code-value,script,style')&&/[\u4e00-\u9fff]/u.test(node.nodeValue))found.push(node.nodeValue.trim());
 return found.filter(Boolean);
}
(async()=>{
 let checked=0;
 for(const [language,pack] of Object.entries(packs)){
  const f=frontend();
  assert.equal(f.run('state.settings.language'),'English','Fresh UI uses English');
  f.run(`state.settings.language=${JSON.stringify(language)};render(true)`);
  assert.ok(!f.run('duration(60)').includes('undefined'));
  if(language==='English')assert.equal(f.run('duration(60)'), '1 hour');
  assert.equal(f.document.documentElement.lang,pack.locale);
  assert.equal(f.document.documentElement.dir,pack.locale==='ar'?'rtl':'ltr');
  for(const page of ['overview','inventory','channels','logs','settings','about']){
   await click(f.document,`[data-page="${page}"]`);
   if(!['简体中文','繁體中文','日本語'].includes(language))assert.deepEqual(untranslated(f.document),[],`${language}: ${page}`);
  }
  await click(f.document,'[data-page="settings"]');
  await click(f.document,'#mode-trigger');
  assert.equal(f.document.querySelector('#mode-trigger').getAttribute('aria-expanded'),'true');
  const opened=f.document.querySelector('#mode-options');
  f.run('render()');
  assert.equal(f.document.querySelector('#mode-options'),opened,'Polling must not replace an open menu');
  await click(f.document,'[data-ui="mode-option"][data-mode="1"]');
  assert.equal(f.run('state.settings.mode'),1);
  assert.equal(f.document.querySelector('#mode-trigger').getAttribute('aria-expanded'),'false');
  await click(f.document,'[data-ui="language-picker"]');
  assert.equal(f.document.querySelectorAll('.language-option').length,20);
  await click(f.document,'[data-ui="choose-language"][data-language="English"]');
  assert.equal(f.run('state.settings.language'),'English');
  assert.equal(f.run('state.active.minutes'),10,'Language change must preserve progress');
  assert.deepEqual(untranslated(f.document),[]);
  f.run(`state.settings.language=${JSON.stringify(language)};render(true)`);
  await click(f.document,'[data-ui="add-game"]');
  const input=f.document.querySelector('#game-input');
  input.value='MiNeCrAfT';input.dispatchEvent(new f.dom.window.Event('input',{bubbles:true}));
  assert.ok([...f.document.querySelectorAll('.game-result')].some(el=>el.dataset.game==='Minecraft Dungeons II'));
  await click(f.document,'[data-ui="close-modal"]');
  await click(f.document,'[data-page="overview"]');
  const activeId=f.run('state.active.id');
  const first=f.document.querySelector('.hero-title').textContent;
  await click(f.document,'[data-ui="hero-next"]');
  assert.notEqual(f.document.querySelector('.hero-title').textContent,first);
  assert.equal(f.run('state.active.id'),activeId,'Carousel must only change the view');
  await click(f.document,'[data-ui="hero-prev"]');
  assert.equal(f.document.querySelector('.hero-title').textContent,first);
  await click(f.document,'[data-ui="details"]');
  assert.equal(f.document.querySelectorAll('.reward-group-progress').length,3);
  assert.ok(f.document.querySelector('[data-ui="cancel-campaign"]'));
  await click(f.document,'[data-ui="cancel-campaign"]');
  if(!['简体中文','繁體中文','日本語'].includes(language))assert.deepEqual(untranslated(f.document),[]);
  await click(f.document,'[data-ui="confirm-cancel-campaign"]');
  assert.equal(f.run('state.campaigns["demo-control"].cancelled'),true);
  assert.equal(f.run('state.settings.priority.includes("CONTROL Resonant")'),true);
  assert.equal(f.run('state.campaigns.demo.finished'),true);
  await click(f.document,'[data-ui="resume-campaign"]');
  assert.equal(f.run('state.campaigns["demo-control"].cancelled'),false);
  assert.equal(f.run('state.active.minutes'),10);
  await click(f.document,'[data-page="inventory"]');
  await click(f.document,'[data-ui="read-code"]');
  assert.equal(f.document.querySelector('#reward-code-value').value,'EXAMPLE-NOT-A-REAL-CODE');
  if(!['简体中文','繁體中文','日本語'].includes(language))assert.deepEqual(untranslated(f.document),[]);
  await click(f.document,'[data-ui="close-modal"]');
  assert.equal(f.document.querySelector('#reward-code-value'),null);
  // Switch back repeatedly; static navigation must retain its original source.
  f.run("state.settings.language='简体中文';render(true)");
  assert.equal(f.document.querySelector('[data-page="inventory"] span').textContent,'活动库存');
  f.dom.window.close();
  checked++;
 }
 console.log(`PASS: ${checked} languages × 6 pages, menus, search, carousel, cancellation/resume and code dialog.`);
})().catch(error=>{console.error(error);process.exitCode=1});
