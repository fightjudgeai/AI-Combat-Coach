import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { FileText, Plus, Trash, Sparkle, SpinnerGap, X } from '@phosphor-icons/react';

const DOC_TYPES = ['bout_agreement', 'venue_contract', 'sponsor_contract', 'medical_form', 'waiver', 'commission_filing'];
const STATUS_COLORS = { draft: 'border-zinc-400 text-zinc-500', sent: 'border-blue-500 text-blue-600', signed: 'border-green-600 text-green-700', filed: 'border-purple-600 text-purple-700' };

export default function DocumentsPage() {
  const { api } = useAuth();
  const [docs, setDocs] = useState([]);
  const [events, setEvents] = useState([]);
  const [fighters, setFighters] = useState([]);
  const [showModal, setShowModal] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [viewDoc, setViewDoc] = useState(null);
  const [form, setForm] = useState({ name: '', type: 'bout_agreement', event_id: '', fighter_id: '', content: '', status: 'draft', notes: '' });

  const load = () => {
    api.get('/documents').then(r => setDocs(r.data)).catch(console.error);
    api.get('/events').then(r => setEvents(r.data)).catch(console.error);
    api.get('/fighters').then(r => setFighters(r.data)).catch(console.error);
  };
  useEffect(() => { load(); }, [api]);

  const handleSubmit = async (e) => { e.preventDefault(); await api.post('/documents', form); setShowModal(false); load(); };

  const generateDoc = async (type, eventId, fighterId = '') => {
    setGenerating(true);
    try {
      const { data } = await api.post(`/documents/generate?type=${type}&event_id=${eventId}&fighter_id=${fighterId}`);
      setViewDoc(data);
      load();
    } catch { alert('Generation failed'); }
    setGenerating(false);
  };

  const deleteDoc = async (id) => { await api.delete(`/documents/${id}`); load(); };
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  return (
    <div data-testid="documents-page" className="animate-in">
      <div className="flex items-center justify-between mb-8">
        <div><h1 className="font-heading text-5xl uppercase leading-none">Documents</h1><p className="text-zinc-500 mt-1">{docs.length} documents</p></div>
        <div className="flex gap-2">
          <button data-testid="create-doc-btn" onClick={() => setShowModal(true)} className="btn-primary flex items-center gap-2"><Plus size={16} weight="bold" /> Manual</button>
          <button data-testid="generate-doc-btn" onClick={() => { if (events[0]) generateDoc('bout_agreement', events[0]._id); }} disabled={generating || events.length === 0} className="btn-gold flex items-center gap-2 disabled:opacity-50">
            {generating ? <SpinnerGap size={16} className="animate-spin" /> : <Sparkle size={16} weight="fill" />} AI Generate
          </button>
        </div>
      </div>

      {/* Quick Generate */}
      <div className="card-brutal p-4 mb-6">
        <p className="font-mono text-xs uppercase text-zinc-500 mb-3">Quick AI Document Generator</p>
        <div className="flex gap-3 items-end">
          <div className="flex-1"><select id="gen-type" className="select-brutal" defaultValue="bout_agreement">{DOC_TYPES.map(t => <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>)}</select></div>
          <div className="flex-1"><select id="gen-event" className="select-brutal"><option value="">Select Event</option>{events.map(e => <option key={e._id} value={e._id}>{e.title}</option>)}</select></div>
          <div className="flex-1"><select id="gen-fighter" className="select-brutal"><option value="">Select Fighter (opt.)</option>{fighters.map(f => <option key={f._id} value={f._id}>{f.name}</option>)}</select></div>
          <button onClick={() => { const t = document.getElementById('gen-type').value; const e = document.getElementById('gen-event').value; const f = document.getElementById('gen-fighter').value; if (e) generateDoc(t, e, f); else alert('Select event'); }} disabled={generating} className="btn-gold flex items-center gap-2 disabled:opacity-50">
            {generating ? <SpinnerGap size={16} className="animate-spin" /> : <Sparkle size={16} weight="fill" />} Generate
          </button>
        </div>
      </div>

      {/* Document List */}
      {docs.length === 0 ? (
        <div className="card-brutal p-12 text-center"><FileText size={48} className="mx-auto mb-4 text-zinc-200" /><p className="font-heading text-3xl uppercase text-zinc-300">No Documents</p></div>
      ) : (
        <div className="space-y-3">
          {docs.map(d => (
            <div key={d._id} className="card-brutal p-4 flex items-center justify-between hover:bg-zinc-50 transition-colors">
              <div className="flex items-center gap-3 flex-1 min-w-0" onClick={() => setViewDoc(d)} style={{ cursor: 'pointer' }}>
                <FileText size={20} weight="bold" className="text-zinc-400 flex-shrink-0" />
                <div className="min-w-0"><p className="font-semibold truncate">{d.name}</p><p className="text-xs text-zinc-500">{d.type?.replace(/_/g, ' ')} | {d.created_at ? new Date(d.created_at).toLocaleDateString() : ''}</p></div>
              </div>
              <div className="flex items-center gap-3">
                <span className={`badge-status text-xs ${STATUS_COLORS[d.status] || ''}`}>{d.status}</span>
                <button onClick={() => deleteDoc(d._id)} className="p-2 hover:text-red-600"><Trash size={14} weight="bold" /></button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* View Document Modal */}
      {viewDoc && (
        <div className="fixed inset-0 modal-overlay flex items-center justify-center z-50 p-4" onClick={() => setViewDoc(null)}>
          <div className="bg-white border-2 border-zinc-950 shadow-[8px_8px_0px_0px_rgba(9,9,11,1)] w-full max-w-3xl max-h-[85vh] overflow-y-auto animate-in" onClick={e => e.stopPropagation()}>
            <div className="bg-zinc-950 text-white p-4 flex items-center justify-between"><h2 className="font-heading text-2xl uppercase truncate">{viewDoc.name}</h2><button onClick={() => setViewDoc(null)}><X size={20} className="text-white" /></button></div>
            <div className="p-6"><pre className="whitespace-pre-wrap text-sm leading-relaxed font-body">{viewDoc.content || 'No content'}</pre></div>
          </div>
        </div>
      )}

      {/* Manual Create Modal */}
      {showModal && (
        <div className="fixed inset-0 modal-overlay flex items-center justify-center z-50 p-4" onClick={() => setShowModal(false)}>
          <div className="bg-white border-2 border-zinc-950 shadow-[8px_8px_0px_0px_rgba(9,9,11,1)] w-full max-w-lg animate-in" onClick={e => e.stopPropagation()}>
            <div className="bg-zinc-950 text-white p-4 flex items-center justify-between"><h2 className="font-heading text-2xl uppercase">New Document</h2><button onClick={() => setShowModal(false)}><X size={20} className="text-white" /></button></div>
            <form onSubmit={handleSubmit} className="p-6 space-y-4">
              <div><label className="font-mono text-xs uppercase text-zinc-500 mb-1 block">Name</label><input value={form.name} onChange={set('name')} className="input-brutal" required /></div>
              <div className="grid grid-cols-2 gap-4"><div><label className="font-mono text-xs uppercase text-zinc-500 mb-1 block">Type</label><select value={form.type} onChange={set('type')} className="select-brutal">{DOC_TYPES.map(t => <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>)}</select></div><div><label className="font-mono text-xs uppercase text-zinc-500 mb-1 block">Status</label><select value={form.status} onChange={set('status')} className="select-brutal"><option value="draft">Draft</option><option value="sent">Sent</option><option value="signed">Signed</option><option value="filed">Filed</option></select></div></div>
              <div><label className="font-mono text-xs uppercase text-zinc-500 mb-1 block">Content</label><textarea value={form.content} onChange={set('content')} className="input-brutal h-32 resize-none" /></div>
              <button type="submit" className="btn-accent w-full text-center">Create Document</button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
