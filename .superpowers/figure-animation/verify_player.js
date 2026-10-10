const fs=require('fs'),vm=require('vm'),assert=require('assert');
const path=process.argv[2]||'reports/figures/reasonlineage-animation-v2/reasonlineage-evolution.html';
const markup=fs.readFileSync(path,'utf8'),script=markup.match(/<script>([\s\S]*)<\/script>/)[1];
function setup(reduced=false){
 const ids=['screen','seek','time','caption','play','prev','next','speed','loop'];
 const elements=Object.fromEntries(ids.map(id=>[id,{value:id==='speed'?'1':'0',checked:id==='loop',innerHTML:'',textContent:'',handlers:{},attrs:{},addEventListener(type,fn){this.handlers[type]=fn},setAttribute(k,v){this.attrs[k]=v}}]));
 const document={getElementById:id=>elements[id],addEventListener(){}};
 const context=vm.createContext({document,window:{matchMedia:()=>({matches:reduced})},requestAnimationFrame(){}});
 vm.runInContext(script,context);return {elements,context,run:s=>vm.runInContext(s,context)};
}
const {elements:e,run}=setup();
assert(run('playing'));assert.equal(run('DATA.frames.length'),376);
assert(e.screen.innerHTML.includes('ReasonLineage'));
e.play.handlers.click();assert(!run('playing'));
e.next.handlers.click();assert.equal(run('position'),3.2);assert(!run('playing'));
e.prev.handlers.click();assert.equal(run('position'),0);
e.seek.value='17.5';e.seek.handlers.input();assert.equal(run('position'),17.5);assert(e.caption.textContent.includes('변이'));
run('position=25;playing=false');e.play.handlers.click();assert.equal(run('position'),0);assert(run('playing'));
e.loop.checked=false;run('position=24.9;playing=true;last=1000;tick(1500)');assert.equal(run('position'),25);assert(!run('playing'));
e.loop.checked=true;run('position=24.9;playing=true;last=1000;tick(1500)');assert(Math.abs(run('position')-.4)<1e-6);assert(run('playing'));
e.speed.value='2';run('position=5;playing=true;last=1000;tick(1500)');assert.equal(run('position'),6);
assert(!setup(true).run('playing'));
for(let i=0;i<14;i++){run(`position=DATA.chapters[${i}][0];paint()`);assert(e.screen.innerHTML.startsWith('<svg'));assert(e.caption.textContent.length>5);}
console.log(JSON.stringify({status:'passed',chapters:14,controls:['play','pause','previous','next','seek','speed','repeat','end','reduced-motion'],actual_browser_automation:false}));
