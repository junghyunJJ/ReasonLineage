const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const text = fs.readFileSync('runs/jev-controlled-2026-10-09/evolution-viewer.html', 'utf8');
const script = text.match(/<script>([\s\S]*)<\/script>/)[1];
const elements = Object.fromEntries(['case','method','arm','summary','stages'].map(id=>[id,{value:'',innerHTML:'',addEventListener(){}}]));
elements.case.value='als';elements.method.value='reasonlineage';elements.arm.value='jev-on';
const context = vm.createContext({document:{getElementById:id=>elements[id]}});
vm.runInContext(script,context);
let checked=0;
for(const caseName of ['als','aml'])for(const method of ['reasonlineage','gpt','grok','glm'])for(const arm of ['jev-on','jev-off']){
  elements.case.value=caseName;elements.method.value=method;elements.arm.value=arm;
  vm.runInContext('render()',context);
  assert.equal((elements.stages.innerHTML.match(/<section class="stage">/g)||[]).length,4);
  assert.equal((elements.stages.innerHTML.match(/<article class="card /g)||[]).length,15); // G0 3 + G1..G3 4 each
  assert.equal((elements.stages.innerHTML.match(/class="card winner"/g)||[]).length,1);
  assert(elements.summary.innerHTML.includes(caseName.toUpperCase()));
  assert(elements.summary.innerHTML.includes(arm));
  checked++;
}
console.log(JSON.stringify({combinations_checked:checked,stages_per_run:4,population_cards_per_run:15,dom_render_logic:'passed',full_browser_screenshot:'not performed'}));
