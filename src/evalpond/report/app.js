(function(){
const D = JSON.parse(document.getElementById('data').textContent);
const P = D.copy.plain, DT = D.copy.details;
const $ = (s,e=document)=>e.querySelector(s);
function h(tag, attrs, ...kids){
  const e=document.createElement(tag);
  for(const [k,v] of Object.entries(attrs||{})){
    if(k==='class')e.className=v; else if(k==='html')e.innerHTML=v; else if(k.startsWith('on'))e.addEventListener(k.slice(2),v); else if(v!==false&&v!=null)e.setAttribute(k,v===true?'':v);
  }
  for(const c of kids.flat(Infinity)){ if(c==null||c===false)continue; e.append(c.nodeType?c:document.createTextNode(c)); }
  return e;
}
const pct=x=>Math.round(x*100)+'%';
const runById=Object.fromEntries(D.runs.map(r=>[r.id,r]));
const taskById=Object.fromEntries(D.tasks.map(t=>[t.id,t]));
function parseHash(){const o={};location.hash.replace(/^#/,'').split('&').filter(Boolean).forEach(p=>{const [k,v]=p.split('=');o[k]=decodeURIComponent(v||'')});return o;}
function go(o){location.hash=Object.entries(o).filter(([,v])=>v).map(([k,v])=>k+'='+encodeURIComponent(v)).join('&');}
const VIEWS=[['summary','Summary'],['compare','Compare runs'],['tasks','Tasks'],['heatmap','Heatmap'],['judge','AI grader'],['about','Details for the curious']];
function explain(key){return h('div',{class:'why'},P[key]);}
function details(key,text){return h('details',null,h('summary',null,'Details for the curious'),h('div',{class:'sub'},text||DT[key]));}
function bar(r){
  const b=h('div',{class:'bar'},h('div',{class:'fill',style:`width:${r.rate*100}%`}));
  b.append(h('div',{class:'rng',style:`left:${r.lo*100}%;width:${(r.hi-r.lo)*100}%`}));return b;
}
function runLabel(id){return runById[id]?runById[id].label:id;}

function viewSummary(){
  const root=h('div');
  root.append(h('h1',null,'How did each run do?'),h('p',{class:'lead'},`${D.manifest.task_count} synthetic tasks about reading income documents. A task counts as right only if every part of the answer is right.`));
  if(!D.runs.length){root.append(h('div',{class:'card'},'No runs yet. Run `evalpond run --model mock-strong` and rebuild the report.'));return root;}
  const g=h('div',{class:'grid'});
  D.runs.forEach(r=>{
    const s=r.summary,o=s.overall;
    const card=h('div',{class:'card'},
      h('h3',null,r.label), h('div',{class:'sub'},`model: ${r.model}${r.repeats>1?` · ${r.repeats} repeats`:''}`),
      h('div',{class:'big'},pct(o.rate)), h('div',{class:'sub'},`${o.k} of ${o.n} answers completely right`), explain('pass_rate'),
      bar(o), h('div',{class:'sub'},`Probably between ${pct(o.lo)} and ${pct(o.hi)}`), explain('range'), details('range'),
      h('h3',{style:'margin-top:14px'},'By kind of task'));
    Object.entries(s.by_category).forEach(([c,v])=>card.append(h('div',null,h('div',{class:'row sub'},h('span',{style:'flex:1'},D.categories[c]||c),h('span',null,`${v.k}/${v.n}`)),bar(v))));
    const meta=h('div',{class:'sub',style:'margin-top:10px'},`Average partial credit ${s.avg_score.toFixed(2)} · cost $${s.cost.toFixed(2)} · ${s.latency.toFixed(1)}s per answer`+(s.errors?` · ${s.errors} errors`:''));
    card.append(meta);
    if(r.repeats>1)card.append(h('div',{class:'sub'},`${s.flaky.length} unstable tasks. `+P.flaky));
    g.append(card);
  });
  root.append(g);
  const sp=h('div',{class:'card'},h('h3',null,'Dev tasks vs held-out test tasks'),explain('split'),
    h('table',null,h('tr',null,h('th',null,'Run'),h('th',null,'Dev'),h('th',null,'Test')),
      D.runs.map(r=>h('tr',null,h('td',null,r.label),h('td',null,fmt(r.summary.by_split.dev)),h('td',null,fmt(r.summary.by_split.test))))));
  root.append(sp);
  return root;
}
function fmt(v){return v?`${pct(v.rate)} (${v.k}/${v.n})`:'-';}

function pick(id,sel,onch){const s=h('select',{id,onchange:onch},D.runs.map(r=>h('option',{value:r.id,selected:r.id===sel},r.label)));return s;}
function viewCompare(q){
  const root=h('div');
  root.append(h('h1',null,'Did the change help?'),h('p',{class:'lead'},'Pick two runs on the same tasks. The verdict says what the evidence supports, in plain words.'));
  if(D.runs.length<2){root.append(h('div',{class:'card'},'Need at least two runs to compare.'));return root;}
  const a=q.a&&runById[q.a]?q.a:D.runs[0].id, b=q.b&&runById[q.b]&&q.b!==a?q.b:D.runs.find(r=>r.id!==a).id;
  const upd=()=>go({view:'compare',a:$('#sa').value,b:$('#sb').value});
  root.append(h('div',{class:'row'},h('span',null,'Before'),pick('sa',a,upd),h('span',null,'After'),pick('sb',b,upd)));
  const c=D.compare[a+'|'+b];
  const cls=c.verdict==='likely better'?'good':c.verdict==='likely worse'?'bad':'warn';
  const word=c.verdict==='likely better'?'Looks better':c.verdict==='likely worse'?'Looks worse':'No clear difference';
  root.append(h('div',{class:'banner '+cls},h('div',{class:'t'},word),h('div',null,c.sentence)));
  root.append(h('div',{class:'row'},
    h('div',{class:'card',style:'flex:1;min-width:140px'},h('div',{class:'big ok'},'+'+c.fixed.length),h('div',null,'fixed'),h('div',{class:'why'},P.fixed)),
    h('div',{class:'card',style:'flex:1;min-width:140px'},h('div',{class:'big no'},'-'+c.regressed.length),h('div',null,'regressed'),h('div',{class:'why'},P.regressed)),
    h('div',{class:'card',style:'flex:1;min-width:140px'},h('div',{class:'big'},Math.round(c.p*100)+'%'),h('div',null,'chance this gap is luck'),h('div',{class:'why'},P.luck))));
  root.append(h('div',{class:'todo'},h('b',null,'What should I do with this? '),c.advice));
  c.notes.forEach(n=>root.append(h('div',{class:'sub'},n)));
  const list=(title,ids,cls2)=>ids.length?h('div',{class:'card'},h('h3',null,title),h('div',null,ids.map(id=>[h('a',{class:'task',href:'#view=tasks&task='+id+'&a='+a+'&b='+b},id),' ']))):null;
  root.append(list('Regressed (right before, wrong now)',c.regressed),list('Fixed (wrong before, right now)',c.fixed));
  root.append(h('details',null,h('summary',null,'Details for the curious'),h('div',{class:'sub'},
    `Exact test on the ${c.fixed.length+c.regressed.length} tasks that flipped: p = ${c.p.toFixed(3)}. Average score change ${c.mean_diff>=0?'+':''}${c.mean_diff.toFixed(3)} (95% range ${c.diff_ci[0].toFixed(3)} to ${c.diff_ci[1].toFixed(3)}). `+DT.luck+' '+DT.gap)));
  return root;
}

function resultsFor(run,tid){return run.results.filter(r=>r.t===tid);}
function viewTasks(q){
  const root=h('div');
  if(q.task&&taskById[q.task])return viewTask(q);
  root.append(h('h1',null,'The tasks'),h('p',{class:'lead'},'Each task tests one thing. Open one to see the document, what a good answer looks like, and how each run did.'));
  const cat=q.cat||'',diff=q.diff||'';
  root.append(h('div',{class:'row'},
    h('select',{onchange:e=>go({view:'tasks',cat:e.target.value,diff})},h('option',{value:''},'All kinds'),Object.entries(D.categories).map(([k,v])=>h('option',{value:k,selected:k===cat},v))),
    h('select',{onchange:e=>go({view:'tasks',cat,diff:e.target.value})},h('option',{value:''},'Any difficulty'),['easy','medium','hard'].map(d=>h('option',{value:d,selected:d===diff},d)))));
  const rows=D.tasks.filter(t=>(!cat||t.category===cat)&&(!diff||t.difficulty===diff));
  const tb=h('table',null,h('tr',null,h('th',null,'Task'),h('th',null,'What it checks'),h('th',null,'Level'),D.runs.map(r=>h('th',null,r.label))));
  rows.forEach(t=>tb.append(h('tr',null,h('td',null,h('a',{class:'task',href:'#view=tasks&task='+t.id},t.id)),h('td',null,t.title),h('td',null,t.difficulty+(t.split==='test'?' · test':'')),
    D.runs.map(r=>{const rs=resultsFor(r,t.id);if(!rs.length)return h('td',null,'-');const p=rs.filter(x=>x.p).length;return h('td',null,h('span',{class:'pill '+(p===rs.length?'good':p===0?'bad':'warn')},p===rs.length?'right':p===0?'wrong':p+'/'+rs.length));}))));
  root.append(h('div',{class:'card'},tb));
  return root;
}
function showGrade(g){
  const box=h('div',{class:'sub',style:'margin:4px 0'});
  if(g.m==='exact'&&g.d.fields){
    const bad=Object.entries(g.d.fields).filter(([,v])=>!v.ok);
    box.append(h('div',null,bad.length?`Wrong: ${bad.length} of ${g.d.fields_total} fields`:`All ${g.d.fields_total} fields right`));
    if(bad.length)box.append(h('table',null,h('tr',null,h('th',null,'Field'),h('th',null,'Should be'),h('th',null,'Got')),bad.map(([k,v])=>h('tr',null,h('td',null,k),h('td',null,JSON.stringify(v.expected)),h('td',{class:'no'},JSON.stringify(v.got))))));
    const all=h('details',null,h('summary',null,'Show every field'),h('table',null,Object.entries(g.d.fields).map(([k,v])=>h('tr',null,h('td',null,k),h('td',null,JSON.stringify(v.expected)),h('td',{class:v.ok?'ok':'no'},JSON.stringify(v.got))))));
    box.append(all);
  }else if(g.m==='rubric'&&g.d.criteria){
    Object.values(g.d.criteria).forEach(c=>box.append(h('div',null,h('span',{class:c.met?'ok':'no'},c.met?'Yes ':'No '),c.text)));
  }else if(g.m==='judge'){
    box.append(h('div',null,h('span',{class:g.s?'ok':'no'},g.s?'AI grader: good answer. ':'AI grader: not good enough. '),g.d.reasoning||''));
  }else if(g.d&&g.d.error){box.append(h('div',{class:'no'},'Error: '+g.d.error));}
  return box;
}
function viewTask(q){
  const t=taskById[q.task],root=h('div');
  root.append(h('p',null,h('a',{href:'#view=tasks'},'< All tasks')),h('h1',null,t.title),
    h('div',{class:'row'},h('span',{class:'pill mute'},t.id),h('span',{class:'pill mute'},D.categories[t.category]),h('span',{class:'pill mute'},t.difficulty),h('span',{class:'pill mute'},t.split==='test'?'held-out test task':'dev task')),
    h('div',{class:'card'},h('h3',null,'Why it matters'),h('div',null,t.why),h('h3',{style:'margin-top:10px'},'What a good answer looks like'),h('div',null,t.good)),
    h('div',{class:'card'},h('h3',null,'The document(s), as plain text'),t.docs.map(d=>h('pre',null,d)),
      h('details',null,h('summary',null,'The correct answer'),h('pre',null,JSON.stringify(t.expected,null,1)))));
  D.runs.forEach(r=>{
    const rs=resultsFor(r,t.id);if(!rs.length)return;
    const card=h('div',{class:'card'},h('h3',null,r.label));
    rs.forEach(x=>{
      card.append(h('div',{class:'row'},h('span',{class:'pill '+(x.p?'good':'bad')},x.p?'Right':'Wrong'),h('span',{class:'sub'},`score ${x.s.toFixed(2)}`+(r.repeats>1?` · repeat ${x.r+1}`:''))));
      x.g.forEach(g=>card.append(showGrade(g)));
      card.append(h('details',null,h('summary',null,'What the model said'),h('pre',null,typeof x.out==='string'?x.out:JSON.stringify(x.out,null,1))));
    });
    root.append(card);
  });
  return root;
}
function color(s){return s>=.999?'#2e8b57':s<=.001?'#d9534f':'#e6b04a';}
function viewHeat(){
  const root=h('div');
  root.append(h('h1',null,'Which tasks tell the runs apart?'),h('p',{class:'lead'},P.heatmap));
  root.append(h('div',{class:'legend sub'},h('span',{style:'background:'+color(1)}),'right',h('span',{style:'background:'+color(.5)}),'partly',h('span',{style:'background:'+color(0)}),'wrong'));
  const tb=h('table',{class:'heat'},h('tr',null,h('td'),D.runs.map(r=>h('td',{class:'sub',style:'max-width:70px;font-size:11px'},r.label))));
  D.tasks.forEach(t=>{
    const tr=h('tr',null,h('td',{class:'tid'},h('a',{class:'task',href:'#view=tasks&task='+t.id},t.id)));
    let mixed=false,first=null;
    D.runs.forEach(r=>{const rs=resultsFor(r,t.id);const s=rs.length?rs.reduce((a,x)=>a+x.s,0)/rs.length:null;if(s!==null){if(first===null)first=s;else if(Math.abs(s-first)>.01)mixed=true;}
      tr.append(h('td',null,s===null?h('span',{class:'cell',style:'background:#eee'}):h('a',{href:'#view=tasks&task='+t.id,title:`${t.id}: ${s.toFixed(2)}`},h('span',{class:'cell',style:'background:'+color(s)}))));});
    tr.append(h('td',{class:'sub'},mixed?'tells runs apart':''));tb.append(tr);
  });
  root.append(h('div',{class:'card',style:'overflow:auto'},tb));return root;
}
function viewJudge(){
  const root=h('div'),j=D.judge_health;
  root.append(h('h1',null,'Can the AI grader be trusted?'),h('p',{class:'lead'},'A few tasks have no crisp right answer, so a second AI grades them. Graders have habits, so we check them against a human.'));
  const c1=h('div',{class:'card'},h('h3',null,'Agreement with a human'));
  if(j.labeled){c1.append(h('div',{class:'big'},`${j.agree} of ${j.labeled}`),h('div',{class:'sub'},'answers where the AI grader and a human agree'),explain('judge_agree'),details('judge_agree',DT.judge_agree+` Measured: ${j.chance_adjusted==null?'n/a':j.chance_adjusted.toFixed(2)}.`));}
  else c1.append(h('div',null,'Not measured yet. Run `evalpond calibrate` to label about 20 answers yourself, then rebuild the report.'),explain('judge_agree'));
  root.append(c1);
  const c2=h('div',{class:'card'},h('h3',null,'Does it favor long answers?'),explain('judge_length'));
  D.runs.forEach(r=>{const v=r.summary.length_corr;c2.append(h('div',null,r.label+': ',v==null?'not enough data':(Math.abs(v)<.2?'no sign of it':'possible length preference')+` (${v.toFixed(2)})`));});
  c2.append(details('judge_length'));root.append(c2);return root;
}
function viewAbout(){
  const root=h('div');
  root.append(h('h1',null,'Details for the curious'),h('p',{class:'lead'},'The technical names behind the plain-language numbers.'));
  const rows=Object.entries(DT).map(([k,v])=>h('tr',null,h('td',null,k.replace('_',' ')),h('td',null,v)));
  root.append(h('div',{class:'card'},h('table',null,rows)));
  root.append(h('div',{class:'card'},h('h3',null,'What this report cannot tell you'),h('div',null,`With ${D.manifest.task_count} tasks, small gaps are noise. This set is for learning how evals work, not for fine decisions. Every document is synthetic. Task set: ${D.manifest.name}, seed ${D.manifest.seed}.`)));
  return root;
}
function render(){
  const q=parseHash(),v=q.view||'summary';
  $('#nav').replaceChildren(...VIEWS.map(([k,l])=>h('a',{href:'#view='+k,class:k===v?'on':''},l)));
  const fn={summary:viewSummary,compare:viewCompare,tasks:viewTasks,heatmap:viewHeat,judge:viewJudge,about:viewAbout}[v]||viewSummary;
  $('#app').replaceChildren(fn(q));
  window.scrollTo(0,0);
}
window.addEventListener('hashchange',render);render();
})();
