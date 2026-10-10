const fs=require('fs'),vm=require('vm'),assert=require('assert');
const path=process.argv[2]||'reports/figures/reasonlineage-lineage-overview/animation.html';
const markup=fs.readFileSync(path,'utf8'),script=markup.match(/<script>([\s\S]*)<\/script>/)[1];
assert(markup.includes('max="28"'));
function setup(reduced=false){
 const ids=['screen','seek','time','caption','play','prev','next','speed','loop'];
 const elements=Object.fromEntries(ids.map(id=>[id,{value:id==='speed'?'1':'0',checked:id==='loop',innerHTML:'',textContent:'',handlers:{},addEventListener(k,f){this.handlers[k]=f},setAttribute(){}}]));
 const context=vm.createContext({document:{getElementById:id=>elements[id],addEventListener(){}},window:{matchMedia:()=>({matches:reduced})},requestAnimationFrame(){}});
 vm.runInContext(script,context);return {elements,run:s=>vm.runInContext(s,context)};
}
const {elements:e,run}=setup();
assert.equal(run('DATA.duration'),28);assert.equal(run('DATA.frames.length'),421);assert.equal(run('DATA.chapters.length'),20);
assert(run('playing'));e.play.handlers.click();assert(!run('playing'));
e.next.handlers.click();assert.equal(run('position'),3);e.prev.handlers.click();assert.equal(run('position'),0);
e.seek.value='19.5';e.seek.handlers.input();assert.equal(run('position'),19.5);assert(e.caption.textContent.includes('답변'));
run('position=28;playing=false');e.play.handlers.click();assert.equal(run('position'),0);assert(run('playing'));
e.loop.checked=false;run('position=27.9;playing=true;last=1000;tick(1500)');assert.equal(run('position'),28);assert(!run('playing'));
e.loop.checked=true;run('position=27.9;playing=true;last=1000;tick(1500)');assert(Math.abs(run('position')-.4)<1e-6);
e.speed.value='2';run('position=1;playing=true;last=1000;tick(1500)');assert.equal(run('position'),2);
assert(!setup(true).run('playing'));
for(let i=0;i<20;i++){run(`position=DATA.chapters[${i}][0];paint()`);assert(e.screen.innerHTML.startsWith('<svg'));assert(e.caption.textContent.length>5);}
console.log(JSON.stringify({status:'passed',chapters:20,frames:421,duration:28,controls:['play','pause','previous','next','seek','speed','repeat','reduced-motion'],actual_browser_automation:false}));
