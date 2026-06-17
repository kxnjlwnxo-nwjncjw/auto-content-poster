/* YouTube Queue Dashboard */

const STATUS_LABELS = {
  draft: 'Draft',
  generating: 'Generating',
  pending_review: 'Pending Review',
  approved: 'Approved',
  posted: 'Posted',
  rejected: 'Rejected',
};

const CATEGORIES = {
  '1': 'Film & Animation', '10': 'Music', '15': 'Pets & Animals',
  '17': 'Sports', '20': 'Gaming', '22': 'People & Blogs',
  '24': 'Entertainment', '25': 'News & Politics', '26': 'Howto & Style',
  '28': 'Science & Technology',
};

// ── State ────────────────────────────────────────────────────────────────────
let currentStatus = '';
let openItemId = null;
let pendingRejectId = null;
let draftEditId = null;

// ── API ──────────────────────────────────────────────────────────────────────
async function api(method, path, body) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
  };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const res = await fetch('/api' + path, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || `HTTP ${res.status}`);
  }
  return res.json();
}

// ── Utilities ────────────────────────────────────────────────────────────────
function esc(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function fmtDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString(undefined, {
    month: 'short', day: 'numeric', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

function thumbSrc(item) {
  if (item.thumbnail_url) return item.thumbnail_url;
  if (item.thumbnail_path) {
    // Higgsfield assets are served from /higgsfield-assets/{id}/{filename}
    const fn = item.thumbnail_path.split('/').pop();
    return `/higgsfield-assets/${item.id}/${fn}`;
  }
  return null;
}

// Return URL for a Higgsfield video asset (intro or scene)
function hfVideoSrc(contentId, filePath) {
  if (!filePath) return null;
  const fn = filePath.split('/').pop();
  return `/higgsfield-assets/${contentId}/${fn}`;
}

// Badge for per-asset approval state
function assetApprovalBadge(state) {
  if (state === true)  return '<span class="badge badge-approved" style="font-size:.7rem">✓ approved</span>';
  if (state === false) return '<span class="badge badge-rejected" style="font-size:.7rem">✕ rejected</span>';
  return '<span class="badge badge-draft" style="font-size:.7rem">pending</span>';
}

// Full Higgsfield section HTML injected into the panel
function higgsFieldSectionHTML(item) {
  const hs = item.higgsfield_status || 'idle';
  const approvals = item.higgsfield_approvals || {};

  let statusMsg = '';
  if (hs === 'generating') {
    statusMsg = `<div class="hf-status generating">⚡ Generating assets — this may take a few minutes…</div>`;
  } else if (hs === 'failed') {
    statusMsg = `<div class="hf-status failed">⚠ Generation failed: ${esc(item.higgsfield_error || 'unknown error')}</div>`;
  }

  // Thumbnail asset
  const thumbHtml = (() => {
    const src = thumbSrc(item);
    if (!src) return '<div class="asset-placeholder">No thumbnail yet</div>';
    return `<img class="hf-asset-img" src="${esc(src)}?t=${Date.now()}" alt="thumbnail">`;
  })();

  // Intro asset
  const introHtml = (() => {
    if (!item.intro_path) return '<div class="asset-placeholder">No intro yet</div>';
    const src = hfVideoSrc(item.id, item.intro_path);
    const ext = item.intro_path.split('.').pop().toLowerCase();
    if (['mp4', 'webm', 'mov'].includes(ext)) {
      return `<video class="hf-asset-vid" controls preload="metadata" src="${esc(src)}"></video>`;
    }
    return `<div class="asset-placeholder mock">Mock intro — add HIGGSFIELD_API_KEY for real video</div>`;
  })();

  // Scene assets
  const scenesHtml = (() => {
    const paths = item.scenes_paths || [];
    if (!paths.length) return '<div class="asset-placeholder">No scenes yet</div>';
    return paths.map((p, i) => {
      const src = hfVideoSrc(item.id, p);
      const ext = p.split('.').pop().toLowerCase();
      if (['mp4', 'webm', 'mov'].includes(ext)) {
        return `<video class="hf-asset-vid" controls preload="metadata" src="${esc(src)}" title="Scene ${i+1}"></video>`;
      }
      return `<div class="asset-placeholder mock">Scene ${i+1}: Mock — add HIGGSFIELD_API_KEY</div>`;
    }).join('');
  })();

  const assetActionsFor = (assetKey) => {
    const state = approvals[assetKey];
    if (state === false) return `<div style="color:var(--text-muted);font-size:.75rem">Re-generating…</div>`;
    return `
      <div class="asset-btn-row">
        <button class="btn-asset-approve btn-success" data-asset="${assetKey}"
          style="${state === true ? 'opacity:.6' : ''}">
          ${state === true ? '✓ Approved' : 'Approve'}
        </button>
        <button class="btn-asset-reject btn-danger-sm" data-asset="${assetKey}">Reject &amp; Regenerate</button>
      </div>`;
  };

  const allApproved = approvals.intro === true && approvals.thumbnail === true && approvals.scenes === true;

  return `
    <div class="hf-section">
      <div class="hf-section-header">
        <strong>Higgsfield AI Assets</strong>
        ${hs === 'generating' ? '<span class="badge badge-generating">generating</span>' : ''}
        ${hs === 'ready' || (item.thumbnail_path || item.intro_path) ? '<span class="badge badge-approved">assets ready</span>' : ''}
        ${hs === 'failed' ? '<span class="badge badge-rejected">failed</span>' : ''}
      </div>
      ${statusMsg}

      <div class="hf-asset-block">
        <div class="hf-asset-label">Thumbnail ${assetApprovalBadge(approvals.thumbnail)}</div>
        ${thumbHtml}
        ${(item.thumbnail_path || item.thumbnail_url) ? assetActionsFor('thumbnail') : ''}
      </div>

      <div class="hf-asset-block">
        <div class="hf-asset-label">Intro Video (5s) ${assetApprovalBadge(approvals.intro)}</div>
        ${introHtml}
        ${item.intro_path ? assetActionsFor('intro') : ''}
      </div>

      <div class="hf-asset-block">
        <div class="hf-asset-label">B-roll Scenes ${assetApprovalBadge(approvals.scenes)}</div>
        ${scenesHtml}
        ${(item.scenes_paths || []).length ? assetActionsFor('scenes') : ''}
      </div>

      ${allApproved && !item.assembled_video_path ? `
        <button class="btn-primary" id="hf-assemble-btn" style="margin-top:12px;width:100%">
          Assemble Video (ffmpeg)
        </button>` : ''}
      ${item.assembled_video_path ? `
        <div class="hf-assembled">
          ✓ Assembled: <span class="filepath">${esc(item.assembled_video_path)}</span>
        </div>` : ''}
    </div>`;
}

let toastTimer = null;
function toast(msg, type = 'info') {
  document.querySelector('.toast')?.remove();
  clearTimeout(toastTimer);
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = msg;
  document.body.appendChild(el);
  toastTimer = setTimeout(() => el.remove(), 3500);
}

// ── Stats ────────────────────────────────────────────────────────────────────
async function refreshStats() {
  try {
    const s = await api('GET', '/stats');
    document.getElementById('stat-pending').textContent = s.pending_review ?? 0;
    document.getElementById('stat-approved').textContent = s.approved ?? 0;
    document.getElementById('stat-posted').textContent = s.posted ?? 0;
  } catch (_) {}
}

// ── Grid ─────────────────────────────────────────────────────────────────────
async function loadContent() {
  const grid = document.getElementById('content-grid');
  grid.innerHTML = '<div class="loading-center"><div class="spinner"></div></div>';
  try {
    const qs = currentStatus ? `?status=${currentStatus}` : '';
    const items = await api('GET', `/content${qs}`);
    renderGrid(grid, items);
    refreshStats();
  } catch (e) {
    grid.innerHTML = `<div class="empty-state"><div class="empty-icon">⚠️</div><p>${esc(e.message)}</p></div>`;
  }
}

function renderGrid(grid, items) {
  if (!items.length) {
    grid.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">📭</div>
        <p>Nothing here yet.</p>
      </div>`;
    return;
  }
  grid.innerHTML = items.map(card).join('');
  grid.querySelectorAll('.card').forEach(el => {
    el.addEventListener('click', () => openPanel(el.dataset.id));
  });
}

function card(item) {
  const src = thumbSrc(item);
  const thumbHtml = src
    ? `<div class="card-thumb"><img src="${esc(src)}" alt="" loading="lazy" onerror="this.parentElement.innerHTML='▶'"></div>`
    : `<div class="card-thumb">▶</div>`;

  const sched = item.scheduled_time
    ? `📅 ${fmtDate(item.scheduled_time)}`
    : '⏰ Immediate on approval';

  return `
    <div class="card" data-id="${esc(item.id)}">
      ${thumbHtml}
      <div class="card-body">
        <div class="card-top">
          <span class="card-title">${esc(item.title)}</span>
          <span class="badge badge-${item.status}">${STATUS_LABELS[item.status] ?? item.status}</span>
        </div>
        <div class="card-meta">
          <span>${sched}</span>
          <span>🔒 ${esc(item.privacy_status)} · ${esc(CATEGORIES[item.category_id] ?? item.category_id)}</span>
        </div>
        ${item.description ? `<p class="card-desc">${esc(item.description)}</p>` : ''}
      </div>
    </div>`;
}

// ── Review panel ─────────────────────────────────────────────────────────────
async function openPanel(id) {
  openItemId = id;
  try {
    const item = await api('GET', `/content/${id}`);
    renderPanel(item);
    document.getElementById('panel').classList.remove('hidden');
    document.getElementById('overlay').classList.remove('hidden');
  } catch (e) {
    toast('Could not load item: ' + e.message, 'error');
  }
}

function closePanel() {
  document.getElementById('panel').classList.add('hidden');
  document.getElementById('overlay').classList.add('hidden');
  openItemId = null;
}

function renderPanel(item) {
  const src = thumbSrc(item);
  const thumbHtml = src
    ? `<img src="${esc(src)}" alt="thumbnail" onerror="this.outerHTML='<div class=no-thumb><span>▶</span><small>No thumbnail</small></div>'">`
    : `<div class="no-thumb"><span>▶</span><small>No thumbnail</small></div>`;

  const tagsHtml = (item.tags ?? []).length
    ? item.tags.map(t => `<span class="tag">${esc(t)}</span>`).join('')
    : '<span class="tag" style="color:var(--text-muted);font-style:italic">No tags</span>';

  let rejectionHtml = '';
  if (item.status === 'rejected' && item.rejection_reason) {
    rejectionHtml = `
      <div class="rejection-box">
        <label>Rejection Reason</label>
        <p>${esc(item.rejection_reason)}</p>
      </div>`;
  }

  let liveHtml = '';
  if (item.status === 'posted' && item.youtube_url) {
    liveHtml = `
      <div class="yt-live-box">
        <label>Live on YouTube</label><br>
        <a href="${esc(item.youtube_url)}" target="_blank" rel="noopener" class="yt-link">
          ▶ ${esc(item.youtube_url)}
        </a>
      </div>`;
  }

  const sourceHtml = (item.video_path || item.video_url) ? `
    <div class="panel-section">
      <label>Video Source</label>
      <div class="source-path">${esc(item.video_path || item.video_url)}</div>
    </div>` : '';

  const notesHtml = item.notes ? `
    <div class="panel-section">
      <label>Internal Notes</label>
      <p>${esc(item.notes)}</p>
    </div>` : '';

  document.getElementById('panel-body').innerHTML = `
    <div class="panel-thumb">${thumbHtml}</div>
    <div class="panel-info">
      <div class="panel-badges">
        <span class="badge badge-${item.status}">${STATUS_LABELS[item.status] ?? item.status}</span>
        <span class="meta-chip">🔒 ${esc(item.privacy_status)}</span>
        <span class="meta-chip">📁 ${esc(CATEGORIES[item.category_id] ?? item.category_id)}</span>
        ${item.scheduled_time ? `<span class="meta-chip">📅 ${fmtDate(item.scheduled_time)}</span>` : '<span class="meta-chip">⏰ Immediate</span>'}
      </div>

      <h3 class="panel-title">${esc(item.title)}</h3>

      ${rejectionHtml}
      ${liveHtml}

      <div class="panel-section">
        <label>Description</label>
        <p>${item.description ? esc(item.description) : '<span class="muted">No description</span>'}</p>
      </div>

      <div class="panel-section">
        <label>Tags</label>
        <div class="tags-row">${tagsHtml}</div>
      </div>

      ${sourceHtml}
      ${notesHtml}

      ${higgsFieldSectionHTML(item)}

      <div class="divider"></div>

      <div class="panel-section">
        <label>Timeline</label>
        <div class="timeline">
          <div class="timeline-row">Created: <span>${fmtDate(item.created_at)}</span></div>
          ${item.submitted_at ? `<div class="timeline-row">Submitted: <span>${fmtDate(item.submitted_at)}</span></div>` : ''}
          ${item.reviewed_at ? `<div class="timeline-row">Reviewed: <span>${fmtDate(item.reviewed_at)}</span></div>` : ''}
          ${item.posted_at ? `<div class="timeline-row">Posted: <span>${fmtDate(item.posted_at)}</span></div>` : ''}
        </div>
      </div>
    </div>`;

  // ── Higgsfield per-asset buttons ──────────────────────────────────────────
  document.querySelectorAll('.btn-asset-approve').forEach(btn => {
    btn.onclick = async () => {
      try {
        await api('POST', `/content/${item.id}/approve-asset`, { asset: btn.dataset.asset });
        const updated = await api('GET', `/content/${item.id}`);
        renderPanel(updated);
      } catch (e) { toast('Approve failed: ' + e.message, 'error'); }
    };
  });

  document.querySelectorAll('.btn-asset-reject').forEach(btn => {
    btn.onclick = async () => {
      try {
        await api('POST', `/content/${item.id}/reject-asset`, { asset: btn.dataset.asset });
        toast(`Regenerating ${btn.dataset.asset}…`, 'info');
        startHfPolling(item.id);
        const updated = await api('GET', `/content/${item.id}`);
        renderPanel(updated);
      } catch (e) { toast('Reject failed: ' + e.message, 'error'); }
    };
  });

  document.getElementById('hf-assemble-btn')?.addEventListener('click', async () => {
    const btn = document.getElementById('hf-assemble-btn');
    btn.disabled = true; btn.textContent = 'Assembling…';
    try {
      await api('POST', `/content/${item.id}/assemble`);
      toast('Video assembled!', 'success');
      const updated = await api('GET', `/content/${item.id}`);
      renderPanel(updated);
    } catch (e) {
      toast('Assembly failed: ' + e.message, 'error');
      btn.disabled = false; btn.textContent = 'Assemble Video (ffmpeg)';
    }
  });

  // If currently generating, auto-poll for status updates
  if (item.higgsfield_status === 'generating') startHfPolling(item.id);

  // Action buttons
  const actions = document.getElementById('panel-actions');
  actions.innerHTML = '';

  if (item.status === 'draft') {
    const needsAssets = !item.higgsfield_status || item.higgsfield_status === 'idle';
    actions.innerHTML = `
      <button class="btn-primary" id="pa-edit">Edit</button>
      <button class="btn-success" id="pa-submit">Submit for Review</button>
      <button class="btn-ghost" id="pa-delete">Delete</button>`;
    document.getElementById('pa-edit').onclick = () => openEditModal(item);
    document.getElementById('pa-submit').onclick = () => submitItem(item.id, item.title);
    document.getElementById('pa-delete').onclick = () => deleteItem(item.id);

  } else if (item.status === 'generating') {
    actions.innerHTML = `<span style="color:var(--text-muted);font-size:.85rem">⚡ Generating AI assets…</span>`;

  } else if (item.status === 'pending_review') {
    const canGenerate = item.higgsfield_status === 'idle' || item.higgsfield_status === 'failed';
    actions.innerHTML = `
      ${canGenerate ? '<button class="btn-secondary" id="pa-gen-assets">Generate AI Assets</button>' : ''}
      <button class="btn-success" id="pa-approve">✓ Approve</button>
      <button class="btn-danger" id="pa-reject">✕ Reject</button>`;
    document.getElementById('pa-gen-assets')?.addEventListener('click', async () => {
      try {
        await api('POST', `/content/${item.id}/generate-assets`);
        toast('Higgsfield generation started!', 'info');
        startHfPolling(item.id);
        const updated = await api('GET', `/content/${item.id}`);
        renderPanel(updated);
      } catch (e) { toast(e.message, 'error'); }
    });
    document.getElementById('pa-approve').onclick = () => approveItem(item.id);
    document.getElementById('pa-reject').onclick = () => openRejectModal(item.id);

  } else if (item.status === 'approved') {
    const schedInfo = item.scheduled_time
      ? `Scheduled for ${fmtDate(item.scheduled_time)} — or post now:`
      : 'Ready to post:';
    actions.innerHTML = `
      <span style="font-size:.8rem;color:var(--text-muted);flex:1">${schedInfo}</span>
      <button class="btn-yt" id="pa-post">▶ Post to YouTube Now</button>`;
    document.getElementById('pa-post').onclick = () => postNow(item.id, item.title);

  } else if (item.status === 'rejected') {
    actions.innerHTML = `
      <button class="btn-primary" id="pa-edit">Edit &amp; Resubmit</button>
      <button class="btn-ghost" id="pa-delete">Delete</button>`;
    document.getElementById('pa-edit').onclick = () => openEditModal(item, true);
    document.getElementById('pa-delete').onclick = () => deleteItem(item.id);

  } else if (item.status === 'posted') {
    actions.innerHTML = `<button class="btn-secondary" id="pa-close">Close</button>`;
    document.getElementById('pa-close').onclick = closePanel;
  }
}

// ── Actions ───────────────────────────────────────────────────────────────────
async function submitItem(id, title) {
  try {
    await api('POST', `/content/${id}/submit`);
    toast(`"${title}" submitted — you'll get a macOS notification.`, 'success');
    closePanel();
    loadContent();
  } catch (e) { toast('Submit failed: ' + e.message, 'error'); }
}

async function approveItem(id) {
  try {
    const item = await api('POST', `/content/${id}/approve`);
    toast('Approved!', 'success');
    renderPanel(item);
    loadContent();
  } catch (e) { toast('Approve failed: ' + e.message, 'error'); }
}

function openRejectModal(id) {
  pendingRejectId = id;
  document.getElementById('reject-reason').value = '';
  document.getElementById('reject-modal').classList.remove('hidden');
}
function closeRejectModal() {
  document.getElementById('reject-modal').classList.add('hidden');
  pendingRejectId = null;
}

async function confirmReject() {
  const reason = document.getElementById('reject-reason').value.trim();
  try {
    const item = await api('POST', `/content/${pendingRejectId}/reject`, { reason });
    closeRejectModal();
    toast('Rejected.', 'info');
    renderPanel(item);
    loadContent();
  } catch (e) { toast('Reject failed: ' + e.message, 'error'); }
}

async function postNow(id, title) {
  if (!confirm(`Post "${title}" to YouTube right now?`)) return;
  const btn = document.getElementById('pa-post');
  if (btn) { btn.disabled = true; btn.textContent = 'Posting…'; }
  try {
    const item = await api('POST', `/content/${id}/post`);
    toast('Posted to YouTube!', 'success');
    renderPanel(item);
    loadContent();
  } catch (e) {
    toast('Post failed: ' + e.message, 'error');
    if (btn) { btn.disabled = false; btn.textContent = '▶ Post to YouTube Now'; }
  }
}

async function deleteItem(id) {
  if (!confirm('Delete this content? This cannot be undone.')) return;
  try {
    await api('DELETE', `/content/${id}`);
    toast('Deleted.', 'info');
    closePanel();
    loadContent();
  } catch (e) { toast('Delete failed: ' + e.message, 'error'); }
}

// ── Draft modal ───────────────────────────────────────────────────────────────
function openNewModal() {
  draftEditId = null;
  document.getElementById('draft-modal-title').textContent = 'New Draft';
  document.getElementById('draft-form').reset();
  document.getElementById('draft-modal').classList.remove('hidden');
}

function openEditModal(item, resetToResubmit = false) {
  draftEditId = item.id;
  document.getElementById('draft-modal-title').textContent =
    resetToResubmit ? 'Edit & Resubmit' : 'Edit Draft';
  const f = document.getElementById('draft-form');
  f.title.value = item.title ?? '';
  f.description.value = item.description ?? '';
  f.video_path.value = item.video_path ?? '';
  f.video_url.value = item.video_url ?? '';
  f.thumbnail_path.value = item.thumbnail_path ?? '';
  f.thumbnail_url.value = item.thumbnail_url ?? '';
  f.tags.value = (item.tags ?? []).join(', ');
  f.privacy_status.value = item.privacy_status ?? 'public';
  f.category_id.value = item.category_id ?? '22';
  f.notes.value = item.notes ?? '';
  if (item.scheduled_time) {
    const local = new Date(new Date(item.scheduled_time).getTime()
      - new Date().getTimezoneOffset() * 60000)
      .toISOString().slice(0, 16);
    f.scheduled_time.value = local;
  } else {
    f.scheduled_time.value = '';
  }
  document.getElementById('draft-modal').classList.remove('hidden');
}

function closeDraftModal() {
  document.getElementById('draft-modal').classList.add('hidden');
  draftEditId = null;
}

document.getElementById('draft-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const f = e.target;
  const submitBtn = document.getElementById('draft-submit');
  submitBtn.disabled = true;
  submitBtn.textContent = 'Saving…';

  const tags = f.tags.value
    ? f.tags.value.split(',').map(t => t.trim()).filter(Boolean)
    : [];

  const scheduledTime = f.scheduled_time.value
    ? new Date(f.scheduled_time.value).toISOString()
    : null;

  const data = {
    title: f.title.value.trim(),
    description: f.description.value.trim(),
    video_path: f.video_path.value.trim(),
    video_url: f.video_url.value.trim(),
    thumbnail_path: f.thumbnail_path.value.trim(),
    thumbnail_url: f.thumbnail_url.value.trim(),
    tags,
    privacy_status: f.privacy_status.value,
    category_id: f.category_id.value,
    scheduled_time: scheduledTime,
    notes: f.notes.value.trim(),
  };

  try {
    if (draftEditId) {
      await api('PUT', `/content/${draftEditId}`, data);
      toast('Updated!', 'success');
      // Re-open the panel with refreshed data
      const updated = await api('GET', `/content/${draftEditId}`);
      renderPanel(updated);
    } else {
      await api('POST', '/content', data);
      toast('Draft created!', 'success');
    }
    closeDraftModal();
    loadContent();
  } catch (err) {
    toast('Save failed: ' + err.message, 'error');
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = 'Save Draft';
  }
});

// ── Wire up static UI ─────────────────────────────────────────────────────────
document.getElementById('btn-new').addEventListener('click', openNewModal);
document.getElementById('panel-close').addEventListener('click', closePanel);
document.getElementById('overlay').addEventListener('click', closePanel);
document.getElementById('draft-modal-close').addEventListener('click', closeDraftModal);
document.getElementById('draft-cancel').addEventListener('click', closeDraftModal);
document.getElementById('reject-modal-close').addEventListener('click', closeRejectModal);
document.getElementById('reject-cancel').addEventListener('click', closeRejectModal);
document.getElementById('reject-confirm').addEventListener('click', confirmReject);

// Tabs
document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    currentStatus = tab.dataset.status;
    loadContent();
  });
});

// Stats bar quick-filters
document.querySelectorAll('.stat[data-filter]').forEach(el => {
  el.addEventListener('click', () => {
    const status = el.dataset.filter;
    document.querySelectorAll('.tab').forEach(t => {
      t.classList.toggle('active', t.dataset.status === status);
    });
    currentStatus = status;
    loadContent();
  });
});

// ── Higgsfield generation polling ─────────────────────────────────────────────
let _hfPollTimer = null;

function startHfPolling(contentId) {
  stopHfPolling();
  _hfPollTimer = setInterval(async () => {
    if (openItemId !== contentId) { stopHfPolling(); return; }
    try {
      const item = await api('GET', `/content/${contentId}`);
      if (item.higgsfield_status !== 'generating') {
        stopHfPolling();
        renderPanel(item);
        loadContent();
      } else {
        // Re-render just the Higgsfield section to show progress
        const hfEl = document.querySelector('.hf-section');
        if (hfEl) hfEl.outerHTML = higgsFieldSectionHTML(item);
      }
    } catch (_) {}
  }, 6000);
}

function stopHfPolling() {
  if (_hfPollTimer) { clearInterval(_hfPollTimer); _hfPollTimer = null; }
}

// Auto-refresh every 30s
setInterval(loadContent, 30_000);
setInterval(refreshStats, 30_000);

// Init
loadContent();
refreshStats();
