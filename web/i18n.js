'use strict';
// Translate UI text only. Data, URLs, game names, identifiers and code values stay intact.
const I18n=(()=>{
 const textSources=new WeakMap(),attributeSources=new WeakMap();
 let language='简体中文',pack={locale:'zh-CN',messages:{}},matcher=null;
 const protectedSelector='[data-i18n-skip],.campaign-game,.campaign-name,.hero-game,.hero-title,.hero-info,.queue-game,.game-result>span,.channel-identity b,.login-code,.reward-code-value,script,style';
 function use(name){if(name===language&&matcher)return;language=DropPilotLocales[name]?name:'English';pack=DropPilotLocales[language];const ordered=Object.keys(pack.messages).sort((a,b)=>b.length-a.length);matcher=new RegExp(ordered.map(k=>k.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')).join('|'),'gu');document.documentElement.lang=pack.locale;document.documentElement.dir=pack.locale==='ar'?'rtl':'ltr'}
 function text(value){if(language==='简体中文')return value;return String(value).replace(matcher,key=>pack.messages[key]??key)}
 function localize(root=document.body){
  const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);let node;
  while(node=walker.nextNode()){
   if(node.parentElement?.closest(protectedSelector))continue;
   let source=textSources.get(node);if(source&&node.nodeValue===source.last&&source.language===language)continue;
   if(!source||node.nodeValue!==source.last)source={original:node.nodeValue};
   source.last=text(source.original);source.language=language;if(node.nodeValue!==source.last)node.nodeValue=source.last;textSources.set(node,source);
  }
  root.querySelectorAll('[title],[placeholder],[aria-label],img[alt]').forEach(el=>{
   if(el.closest(protectedSelector))return;
   let sources=attributeSources.get(el)||{};
   for(const key of ['title','placeholder','aria-label','alt']){if(!el.hasAttribute(key))continue;let source=sources[key];const value=el.getAttribute(key);if(source&&value===source.last&&source.language===language)continue;if(!source||value!==source.last)source={original:value};source.last=text(source.original);source.language=language;if(value!==source.last)el.setAttribute(key,source.last);sources[key]=source}
   attributeSources.set(el,sources);
  });
 }
 return {use,text,localize,get locale(){return pack.locale},get language(){return language}};
})();
