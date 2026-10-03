let folder = new URLSearchParams(location.search).get('folder') || 'inbox';
if (!['inbox','archive','trash'].includes(folder)) folder = 'inbox';
const el = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const chips = choices => choices.map(c => `<span class="choice">${esc(c)}</span>`).join('');
let previous = '';
let generation = 0;
let inFlight = false;
async function refresh() {
 if (inFlight) return;
 inFlight = true;
 const current = ++generation;
 try {
  const responses = await Promise.all(['/api/context',`/api/messages?folder=${folder}`,'/api/decisions'].map(p=>fetch(p,{cache:'no-store'})));
  if (responses.some(r=>!r.ok)) throw new Error('Workspace unavailable');
  const [context,messages,decisions] = await Promise.all(responses.map(r=>r.json()));
  if (current !== generation) return;
  el('objective').textContent=context.objective;
  document.querySelectorAll('[data-folder]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.folder===folder)));
  el('messages').innerHTML=messages.length ? messages.map(m=>`<article class="message"><div class="meta"><b>${esc(m.sender)}</b><span>${esc(m.classification)} / important</span><span>v${m.version} · ${esc(m.folder)}</span></div><h3>${esc(m.subject)}</h3><p>${esc(m.body)}</p><div class="meta"><span>Thread resolved: ${m.resolved?'yes':'no'}</span><span>Outstanding obligation: ${m.outstanding_obligation?'yes':'no'}</span><span>${m.flagged?'Flagged':'Not flagged'}</span></div></article>`).join('') : `<p class="empty">${folder==='inbox'?'No messages in the active inbox. Check Archive to verify preserved correspondence.':'No messages in this folder.'}</p>`;
  const d=decisions[0];
  if(d){
   el('activity').textContent=typeof d.agent_activity==='string' ? d.agent_activity : `Guarded inbox request received${d.agent_activity?.agent?' from '+d.agent_activity.agent:''}.${d.agent_activity?.requested_action?' Agent requested '+d.agent_activity.requested_action+'.':''} Bounded alternatives below; the executor owns the final operation.`;
   el('proposed').innerHTML=chips(d.worker_proposed_choices);
   const key=JSON.stringify(d);
   if(key!==previous){
    previous=key;el('status').textContent=d.status.replaceAll('_',' ');el('status').className='badge '+d.status;
    el('audit').innerHTML=`<div class="id">Decision ${esc(d.decision_id)}</div><div class="timeline">${d.stages.map(s=>`<span>${esc(s)}</span>`).join('')}</div>
    <div class="step"><h3>Trusted business state</h3><div class="facts"><div><span>Sender / classification</span>${esc(d.trusted_state.sender)} / ${esc(d.trusted_state.classification)}</div><div><span>Thread / obligations</span>${d.trusted_state.resolved?'Resolved':'Open'} / ${d.trusted_state.outstanding_obligation?'outstanding':'none'}</div><div><span>Folder / version</span>${esc(d.before.folder)} / ${d.before.version}</div><div><span>Source</span>Authoritative business database</div></div></div>
    <div class="step"><h3>Company policy constrained the options</h3>${d.excluded.map(x=>`<p><span class="choice removed">${esc(x.candidate)}</span> ${esc(x.reason)}</p><div class="id">${esc(x.rule)}</div>`).join('')||'<p>No candidates excluded.</p>'}<div class="choices">${chips(d.permitted_candidates.map(x=>x.id))}</div></div>
    <div class="step"><h3>mini-Jev selected <strong>${esc(d.selected_candidate||'—')}</strong></h3><table class="scores" aria-label="Actual model candidate scores"><tbody>${(d.model_output?.options||[]).map(o=>`<tr class="${o.id===d.selected_candidate?'selected':''}"><td>${esc(o.id)}</td><td>${Number(o.probability).toFixed(6)}</td></tr>`).join('')}</tbody></table><p class="meta">Actual candidate probabilities · uncalibrated</p><div class="id">${esc(d.model_output?.model||'Model result pending')}</div></div>
    <div class="step"><h3>Exact approved operation</h3><pre>${esc(JSON.stringify(d.approved_action||{},null,2))}</pre></div>
    <div class="step"><h3>Committed and independently verified</h3>${d.receipt?`<p>${esc(d.receipt.action.operation)} · ${esc(d.before.folder)} → <strong>${esc(d.after.folder)}</strong> · v${d.before.version} → v${d.after.version}</p><p>Approved/executed match: ${d.verification?.approved_executed_match?'yes':'not verified'}<br>Content unchanged: ${d.verification?.content_unchanged?'yes':'not verified'}</p><div class="id">Receipt ${esc(d.receipt.decision_id)}</div>`:'<p>No inbox mutation committed.</p>'}${d.error?`<p class="error">${esc(d.error)}</p>`:''}</div>
    <div class="step"><div class="facts"><div><span>Model request</span>${Number(d.model_latency_ms||0).toFixed(1)} ms</div><div><span>Full gateway</span>${d.gateway_latency_ms?Number(d.gateway_latency_ms).toFixed(1)+' ms':'In progress'}</div></div></div>`;
   }
  }
  el('connection').textContent='Live view of persisted local state';el('connection').className='';
 }catch(error){el('connection').textContent='Connection lost. Showing the last received state; retrying automatically.';el('connection').className='error';}
 finally { inFlight = false; }
}
document.querySelectorAll('[data-folder]').forEach(b=>b.addEventListener('click',()=>{folder=b.dataset.folder;generation++;history.replaceState(null,'',`?folder=${folder}`);refresh();}));
refresh();setInterval(refresh,1200);
