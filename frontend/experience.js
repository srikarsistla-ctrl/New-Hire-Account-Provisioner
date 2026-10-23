/* Interface helpers. Account changes remain behind the server's approval gate. */
function accessDescription(role) {
  return {viewer:'Read only',guest:'Limited access',basic:'Basic meetings',member:'Everyday access',editor:'Make changes',licensed:'Paid meeting features',standard:'Everyday access',developer:'Development access',admin:'Manage users & settings'}[role] || role;
}

function toast(message, action, label = 'Undo') {
  const box = document.querySelector('#feedback');
  box.replaceChildren();
  const text = document.createElement('span');
  text.textContent = message;
  box.append(text);
  if (action) {
    const button = document.createElement('button');
    button.textContent = label;
    button.onclick = () => { action(); box.hidden = true; };
    box.append(button);
  }
  const close = document.createElement('button');
  close.textContent = '×';
  close.setAttribute('aria-label', 'Dismiss notification');
  close.onclick = () => { box.hidden = true; };
  box.append(close);
  box.hidden = false;
}

function setBusy(on, message) {
  const overlay = document.querySelector('#busy');
  if (on) {
    document.querySelector('#busy-message').textContent = message;
    if (!overlay.open) overlay.showModal();
  } else if (overlay.open) overlay.close();
}

function enhanceShell() {
  const app = document.querySelector('#app');
  app.insertAdjacentHTML('afterbegin', '<a href="#main" class="skip-link">Skip to main content</a>');
  document.querySelector('.topbar').insertAdjacentHTML('afterend', `<nav class="mobile-nav" aria-label="Main navigation"><a href="/" ${page==='new'?'aria-current="page"':''}>＋ New employee</a><a href="/dashboard" ${page==='dashboard'?'aria-current="page"':''}>▦ Requests & results</a><button id="mobile-settings">Demo settings</button></nav>`);
  document.querySelector('#mobile-settings').onclick = toggleSimulator;
  document.querySelectorAll('.navlink.active').forEach(a => a.setAttribute('aria-current','page'));
  app.insertAdjacentHTML('beforeend', `<div class="toast" id="feedback" role="status" hidden></div><dialog id="help-dialog" class="guide-dialog" aria-labelledby="guide-title"><form method="dialog"><button class="dialog-close" aria-label="Close guide">×</button></form><span class="eyebrow">A LITTLE GUIDANCE</span><h2 id="guide-title">One employee. All their apps.</h2><p>This demo helps you set up work accounts in one place.</p><ol class="guide-steps"><li><b>Tell us who’s joining</b><p>Enter fictional details and choose their apps.</p></li><li><b>Check and approve</b><p>Review permissions and any issues. Accounts stay unchanged until you approve.</p></li><li><b>See what happened</b><p>Find approved and rejected requests in Requests & results. Everything is saved.</p></li></ol><div class="glossary"><p><b>Access level (role)</b> — what a person can do inside an app.</p><p><b>Available space (seat)</b> — room for one more user in the app.</p></div><div class="notice"><strong>Practice safely:</strong> These are simulated apps. No real work accounts are created.</div><form method="dialog"><button class="primary guide-done">Got it, let’s start →</button></form></dialog><dialog id="busy" class="busy-dialog" aria-labelledby="busy-message"><span class="spinner" aria-hidden="true"></span><h2 id="busy-message">Working…</h2><p>Please keep this page open. We’ll show the result here.</p></dialog><dialog id="reject-dialog" class="guide-dialog" aria-labelledby="reject-title"><span class="eyebrow">REJECT REQUEST</span><h2 id="reject-title">Close this request?</h2><p>No accounts will be created. The rejected request will stay in your history. To change an app instead, go back and edit the plan.</p><div class="actions"><button id="cancel-reject" autofocus>Keep reviewing</button><button id="confirm-reject" class="danger-solid">Reject request</button></div></dialog>`);
  const guide = document.querySelector('#help-dialog');
  document.querySelector('#help-open').onclick = () => guide.showModal();
  document.querySelector('#busy').addEventListener('cancel', e => e.preventDefault());
  const reject = document.querySelector('#reject-dialog');
  document.querySelector('#cancel-reject').onclick = () => reject.close();
  document.querySelector('#confirm-reject').onclick = () => { reject.close(); decision('reject'); };
  window.addEventListener('beforeunload', e => { if (dirty) { e.preventDefault(); e.returnValue=''; } });
}

function confirmRejection() { document.querySelector('#reject-dialog').showModal(); }

function enhanceHire(form, summarize) {
  addRecommendationFlow(form, summarize);
  addAccessModeSwitcher(form);
  const descriptions = {google_workspace:'Email, documents & calendars',slack:'Team messaging & conversations',github:'Code & collaboration',jira:'Projects & task tracking',confluence:'Team knowledge & documents',zoom:'Video meetings',salesforce:'Customers & sales',aws_iam:'Cloud services & resources'};
  document.querySelectorAll('.tool-card').forEach(card => {
    const key = card.dataset.tool;
    const t = catalog.find(t => t.id === key);
    card.querySelector('.tool-top').insertAdjacentHTML('afterend', `<p class="app-description">${descriptions[key]}</p>`);
    card.insertAdjacentHTML('beforeend', `<p class="permission-note" id="permission-${key}"></p>`);
    const select = card.querySelector('select');
    select.setAttribute('aria-describedby', `permission-${key}`);
    const update = () => {
      const selected = card.querySelector('input').checked;
      const elevated = selected && select.value !== t.roles[0];
      const note = card.querySelector('.permission-note');
      note.textContent = elevated ? 'Higher access requested' : '';
      note.hidden = !elevated;
      note.classList.toggle('elevated', elevated);
    };
    form.addEventListener('input', update);
    form.addEventListener('access-summary', update);
    update();
  });
  const summary = document.querySelector('.aside-card');
  summary.querySelector('.aside-title h3').textContent = 'Request summary';
  const email = form.elements.email;
  email.addEventListener('input', () => {
    const valid = !email.value || /@(example\.com|example\.org|example\.net)$/i.test(email.value.trim());
    email.setCustomValidity(valid ? '' : 'Use a demo email such as alex@example.com.');
  });
  // Buttons that change selections programmatically also update the explanatory copy.
  for (const selector of ['#select-all','#sample']) {
    const button = document.querySelector(selector);
    const previous = button.onclick;
    button.onclick = () => {
      if (selector === '#sample' && [...new FormData(form).values()].some(Boolean) && !window.confirm('Replace the entered employee details with a fictional sample?')) return;
      previous();
      if (selector === '#sample') {
        catalog.forEach((t,i) => { document.querySelector(`#check-${t.id}`).checked = i < 4; document.querySelector(`#role-${t.id}`).value=t.roles[0]; });
        const today = new Date();
        form.elements.start_date.value = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}-${String(today.getDate()).padStart(2,'0')}`;
        email.setCustomValidity('');
        toast('Sample employee added with four starter apps. You can change any detail.');
      }
      summarize();
      form.dispatchEvent(new Event('access-summary'));
    };
  }
}

function addAccessModeSwitcher(form) {
  const manual = form.querySelector('.tool-grid').closest('.panel');
  const recommended = form.querySelector('.recommendation-panel');
  manual.id = 'manual-access-panel';
  recommended.id = 'recommended-access-panel';
  manual.setAttribute('role','tabpanel');
  manual.setAttribute('aria-labelledby','manual-mode');
  recommended.setAttribute('role','tabpanel');
  recommended.setAttribute('aria-labelledby','recommended-mode');
  recommended.insertAdjacentHTML('beforebegin', `<div class="access-tabs" role="tablist" aria-label="Choose how to select access"><button type="button" role="tab" id="manual-mode" aria-controls="manual-access-panel" aria-selected="true">Choose apps manually</button><button type="button" role="tab" id="recommended-mode" aria-controls="recommended-access-panel" aria-selected="false" tabindex="-1">Get recommendations</button></div>`);
  const manualButton = document.querySelector('#plan-button');
  const recommendButton = document.querySelector('#recommend-access');
  manualButton.after(recommendButton);
  recommended.querySelector('.actions').remove();
  const tabs = [document.querySelector('#manual-mode'), document.querySelector('#recommended-mode')];
  function selectMode(index) {
    const ai = index === 1;
    manual.hidden = ai;
    recommended.hidden = !ai;
    manualButton.hidden = ai;
    recommendButton.hidden = !ai;
    document.querySelector('#responsibilities').disabled = !ai;
    document.querySelector('#summary-count').closest('.summary-line').hidden = ai;
    document.querySelector('#summary-icons').hidden = ai;
    tabs.forEach((tab,i) => { tab.setAttribute('aria-selected', String(i===index)); tab.tabIndex=i===index?0:-1; });
  }
  tabs.forEach((tab,index) => {
    tab.onclick=()=>selectMode(index);
    tab.onkeydown=e=>{
      if(!['ArrowLeft','ArrowRight','Home','End'].includes(e.key)) return;
      e.preventDefault();
      const next=e.key==='Home'?0:e.key==='End'?1:1-index;
      selectMode(next);tabs[next].focus();
    };
  });
  // Enter must submit the active path, never hidden manual selections.
  const manualSubmit = form.onsubmit;
  form.onsubmit = event => {
    if (!recommended.hidden) { event.preventDefault(); recommendButton.click(); }
    else manualSubmit(event);
  };
  selectMode(0);
}

function enhanceApproval(markDirty) {
  const total = current.plan.length;
  const blocked = current.plan.filter(s => !s.exists && s.seats.used >= s.seats.total).length;
  const elevated = current.plan.filter(s => s.role !== catalog.find(t => t.id===s.tool).roles[0]).length;
  document.querySelector('.steps').insertAdjacentHTML('afterend', `<div class="review-overview"><div><strong>${total}</strong><span>apps to review</span></div><div><strong>${current.plan.filter(s=>s.exists).length}</strong><span>existing accounts to reuse</span></div><div class="${blocked?'attention':''}"><strong>${blocked}</strong><span>apps without available space</span></div><div class="${elevated?'attention':''}"><strong>${elevated}</strong><span>higher access requests</span></div></div>`);
  const edit = document.querySelector('#save-plan');
  edit.insertAdjacentHTML('afterend', '<button id="reset-plan" class="text-button" hidden>Discard unsaved changes</button>');
  document.querySelector('#reset-plan').onclick = () => { renderApproval(); document.querySelector('#feedback').hidden=true; };
  const update = () => {
    document.querySelector('#reset-plan').hidden = !dirty;
    document.querySelector('#edit-note').classList.toggle('unsaved',dirty);
  };
  document.querySelector('#assignments').addEventListener('change', update);
  document.querySelector('#feedback').addEventListener('click', update, {once:true});
  document.querySelector('#assignments').addEventListener('click', () => queueMicrotask(update));
  document.querySelectorAll('.review-row').forEach(row => {
    const s = current.plan.find(s=>s.tool===row.dataset.tool);
    const explanation = document.createElement('div');
    explanation.className='recommendation-reason';
    const title = document.createElement('strong');
    title.textContent = 'Reason';
    const text = document.createElement('p');
    text.textContent = s.reason || 'Previously selected access. Check that it is needed for the job.';
    explanation.append(title, text);
    if (s.recommendation_source) row.querySelector('.review-top').after(explanation);
    if (!s.exists && s.seats.used >= s.seats.total) row.classList.add('capacity-warning');
    row.querySelector('select').insertAdjacentHTML('afterend', '<span class="sr-only">Changing this requires saving and reviewing the plan again.</span>');
  });
}

function addRecommendationFlow(form, summarize) {
  form.querySelector('.panel').insertAdjacentHTML('afterend', `<section class="panel recommendation-panel"><div class="panel-head"><div><h2>Recommend access</h2><p>Describe the role to get application and permission suggestions.</p></div></div><div class="panel-body"><label class="field" for="responsibilities">What will this employee work on?</label><textarea id="responsibilities" rows="3" minlength="10" maxlength="2000" placeholder="For example: Build web applications, review code, and update engineering tasks."></textarea><div class="actions"><button type="button" class="primary" id="recommend-access">Suggest access</button></div><p class="field-help">Recommendations require your review and approval.</p><details class="policy-details"><summary>View company access policy</summary><div id="policy-info">Select a department to see its policy.</div></details></div></section>`);
  let policyRequest=0;
  const refreshPolicy = async () => {
    const request = ++policyRequest;
    const department = form.elements.department.value;
    if(!department) return;
    try {
      const policy = await api(`/api/hires/policy?department=${encodeURIComponent(department)}`);
      if(request!==policyRequest) return;
      document.querySelector('#policy-info').innerHTML = `<p>${esc(policy.description)}</p><ul>${catalog.map(t=>`<li><b>${esc(t.name)}:</b> ${policy.tools[t.id].map(esc).join(', ')}</li>`).join('')}</ul>`;
      catalog.forEach(t => {
        const select = document.querySelector(`#role-${t.id}`);
        for(const option of select.options) option.disabled=!policy.tools[t.id].includes(option.value);
        if(!policy.tools[t.id].includes(select.value)) select.value=t.roles[0];
      });
      summarize();
      form.dispatchEvent(new Event('access-summary'));
    } catch(e) { document.querySelector('#policy-info').textContent='Policy could not be loaded. The server will still validate your request.'; }
  };
  form.elements.department.addEventListener('change',refreshPolicy);
  document.querySelector('#sample').addEventListener('click',()=>queueMicrotask(refreshPolicy));
  document.querySelector('#recommend-access').onclick = async () => {
    clearError();
    if(!form.reportValidity()) return;
    const responsibilities=document.querySelector('#responsibilities');
    if(responsibilities.value.trim().length<10){responsibilities.focus();error(new Error('Describe the employee’s responsibilities in at least 10 characters.'));return;}
    const button=document.querySelector('#recommend-access');
    button.disabled=true;
    setBusy(true,'Recommending apps and checking company policy…');
    try {
      const data=Object.fromEntries(new FormData(form));
      data.responsibilities=responsibilities.value.trim();
      const hire=await api('/api/hires/recommend',{method:'POST',body:JSON.stringify(data)});
      location.href=`/approval?id=${hire.id}`;
    } catch(e) { setBusy(false);error(e); }
    finally { button.disabled=false;setBusy(false); }
  };
}

function enhanceDashboard(hires) {
  const panel = document.querySelector('#view .panel');
  const controls = `<div class="request-controls"><label class="search-field"><span aria-hidden="true">⌕</span><input id="request-search" type="search" placeholder="Search name, email, or department" aria-label="Search requests"></label><label class="filter-field"><span class="sr-only">Filter by status</span><select id="request-filter"><option value="all">All statuses</option><option value="pending_approval">Awaiting approval</option><option value="completed">Completed</option><option value="completed_with_issues">Needs attention</option><option value="rejected">Rejected</option></select></label><span id="request-count" role="status"></span></div>`;
  panel.querySelector('.panel-head').insertAdjacentHTML('afterend', controls);
  panel.insertAdjacentHTML('beforeend','<div id="no-matches" class="empty" hidden><h3>No matching requests</h3><p>Try another name or choose a different status.</p><button id="clear-filters">Clear filters</button></div>');
  function filter() {
    const query = document.querySelector('#request-search').value.trim().toLowerCase();
    const status = document.querySelector('#request-filter').value;
    let count=0;
    hires.forEach(h => {
      const show = `${h.full_name} ${h.email} ${h.department}`.toLowerCase().includes(query) && (status==='all'||h.status===status);
      const row = document.querySelector(`[data-request-id="${h.id}"]`);
      if(row) row.hidden=!show;
      if(show) count++;
    });
    document.querySelector('#request-count').textContent=`${count} of ${hires.length} requests`;
    document.querySelector('#no-matches').hidden=count!==0||hires.length===0;
  }
  document.querySelector('#request-search').oninput=filter;
  document.querySelector('#request-filter').onchange=filter;
  document.querySelector('#clear-filters').onclick=()=>{document.querySelector('#request-search').value='';document.querySelector('#request-filter').value='all';filter();};
  filter();
}

function enhanceResults(h) {
  const state = h.status;
  const heading = state==='completed'?'All selected apps are ready':state==='rejected'?'Request closed without changes':'Some apps need a follow-up';
  const detail = state==='completed'?'The approved accounts and team groups are set up in this demo. You can download the record below.':state==='rejected'?'Your decision has been saved. To request different access, start a new employee request.':'Read the affected app’s explanation below. After fixing the issue in Demo settings, submit a new request. Existing accounts will be reused.';
  document.querySelector('.status-banner')?.remove();
  document.querySelector('.steps').insertAdjacentHTML('afterend', `<section class="outcome ${state}"><span class="outcome-mark" aria-hidden="true">${state==='completed'?'✓':state==='rejected'?'×':'!'}</span><div><h2>${heading}</h2><p>${detail}</p></div><a class="button" href="/">New request →</a></section>`);
  if(state==='rejected') document.querySelector('.stats').hidden=true;
  const logPanel = document.querySelector('#download').closest('.panel');
  const entries = [...logPanel.querySelectorAll('.log')];
  const details = document.createElement('details');
  details.className='audit-details';
  const summary = document.createElement('summary');
  summary.textContent=`Show ${entries.length} activity entries`;
  details.append(summary,...entries);
  logPanel.append(details);
  document.querySelectorAll('.table-wrap').forEach(table=>{table.tabIndex=0;table.setAttribute('aria-label','App results, scroll horizontally if needed');});
}
