import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Plus, Trash, X, PencilSimple, Handshake } from '@phosphor-icons/react';

const TIERS = ['platinum', 'gold', 'silver', 'bronze'];
const STATUSES = ['prospect', 'contacted', 'negotiating', 'confirmed', 'active', 'inactive'];

export default function SponsorsPage() {
  const { api } = useAuth();
  const [sponsors, setSponsors] = useState([]);
  const [events, setEvents] = useState([]);
  const [showModal, setShowModal] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(emptyForm());

  function emptyForm() {
    return { name: '', contact_name: '', contact_email: '', phone: '', tier: 'silver', amount: 0, status: 'prospect', notes: '', event_ids: [] };
  }

  const load = () => {
    api.get('/sponsors').then(r => setSponsors(r.data));
    api.get('/events').then(r => setEvents(r.data));
  };
  useEffect(() => { load(); }, []);

  const openCreate = () => { setEditing(null); setForm(emptyForm()); setShowModal(true); };
  const openEdit = (s) => {
    setEditing(s._id);
    setForm({ name: s.name, contact_name: s.contact_name || '', contact_email: s.contact_email || '', phone: s.phone || '', tier: s.tier || 'silver', amount: s.amount || 0, status: s.status || 'prospect', notes: s.notes || '', event_ids: s.event_ids || [] });
    setShowModal(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const payload = { ...form, amount: parseFloat(form.amount) || 0 };
    if (editing) await api.put(`/sponsors/${editing}`, payload);
    else await api.post('/sponsors', payload);
    setShowModal(false);
    load();
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Remove this sponsor?')) return;
    await api.delete(`/sponsors/${id}`);
    load();
  };

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const tierColors = { platinum: 'bg-zinc-200 text-zinc-800', gold: 'bg-[#D4AF37] text-zinc-950', silver: 'bg-zinc-300 text-zinc-700', bronze: 'bg-amber-700 text-white' };
  const totalValue = sponsors.reduce((sum, s) => sum + (s.amount || 0), 0);

  return (
    <div data-testid="sponsors-page" className="animate-in">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="font-heading text-5xl uppercase leading-none">Sponsors</h1>
          <p className="text-zinc-500 mt-1">{sponsors.length} sponsors | ${totalValue.toLocaleString()} total value</p>
        </div>
        <button data-testid="add-sponsor-btn" onClick={openCreate} className="btn-accent flex items-center gap-2">
          <Plus size={18} weight="bold" /> Add Sponsor
        </button>
      </div>

      {sponsors.length === 0 ? (
        <div className="card-brutal p-12 text-center">
          <Handshake size={48} weight="bold" className="mx-auto mb-4 text-zinc-200" />
          <p className="font-heading text-3xl uppercase text-zinc-300 mb-2">No Sponsors Yet</p>
          <p className="text-zinc-500">Start building your sponsor network</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
          {sponsors.map(s => (
            <div key={s._id} data-testid={`sponsor-card-${s._id}`} className="card-brutal overflow-hidden">
              <div className="flex items-center justify-between p-4 border-b-2 border-zinc-100">
                <div>
                  <h3 className="font-semibold text-lg">{s.name}</h3>
                  {s.contact_name && <p className="text-sm text-zinc-500">{s.contact_name}</p>}
                </div>
                <span className={`font-heading uppercase text-sm px-3 py-1 ${tierColors[s.tier] || 'bg-zinc-100'}`}>
                  {s.tier}
                </span>
              </div>
              <div className="p-4">
                <div className="flex items-center justify-between mb-3">
                  <span className="font-heading text-2xl">${(s.amount || 0).toLocaleString()}</span>
                  <span className={`badge-status text-xs ${s.status === 'active' || s.status === 'confirmed' ? 'border-green-600 text-green-700' : 'border-zinc-400 text-zinc-500'}`}>
                    {s.status}
                  </span>
                </div>
                {s.contact_email && <p className="text-sm text-zinc-500 mb-1">{s.contact_email}</p>}
                {s.notes && <p className="text-sm text-zinc-400 truncate">{s.notes}</p>}
                <div className="flex gap-2 mt-4">
                  <button data-testid={`edit-sponsor-${s._id}`} onClick={() => openEdit(s)} className="btn-primary text-sm py-2 px-4 flex-1">Edit</button>
                  <button data-testid={`delete-sponsor-${s._id}`} onClick={() => handleDelete(s._id)} className="border-2 border-zinc-950 px-3 py-2 hover:bg-red-50 hover:border-red-500 transition-colors">
                    <Trash size={16} weight="bold" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {showModal && (
        <div className="fixed inset-0 modal-overlay flex items-center justify-center z-50 p-4" onClick={() => setShowModal(false)}>
          <div className="bg-white border-2 border-zinc-950 shadow-[8px_8px_0px_0px_rgba(9,9,11,1)] w-full max-w-lg max-h-[90vh] overflow-y-auto animate-in" onClick={e => e.stopPropagation()}>
            <div className="bg-zinc-950 text-white p-4 flex items-center justify-between">
              <h2 className="font-heading text-2xl uppercase">{editing ? 'Edit Sponsor' : 'Add Sponsor'}</h2>
              <button data-testid="close-sponsor-modal" onClick={() => setShowModal(false)}><X size={20} className="text-white" /></button>
            </div>
            <form onSubmit={handleSubmit} className="p-6 space-y-4">
              <div>
                <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Company Name</label>
                <input data-testid="sponsor-name-input" value={form.name} onChange={set('name')} className="input-brutal" placeholder="Monster Energy" required />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Contact Name</label>
                  <input data-testid="sponsor-contact-input" value={form.contact_name} onChange={set('contact_name')} className="input-brutal" placeholder="John Smith" />
                </div>
                <div>
                  <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Email</label>
                  <input data-testid="sponsor-email-input" type="email" value={form.contact_email} onChange={set('contact_email')} className="input-brutal" placeholder="john@monster.com" />
                </div>
              </div>
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Tier</label>
                  <select data-testid="sponsor-tier-select" value={form.tier} onChange={set('tier')} className="select-brutal">
                    {TIERS.map(t => <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>)}
                  </select>
                </div>
                <div>
                  <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Amount ($)</label>
                  <input data-testid="sponsor-amount-input" type="number" value={form.amount} onChange={set('amount')} className="input-brutal" />
                </div>
                <div>
                  <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Status</label>
                  <select data-testid="sponsor-status-select" value={form.status} onChange={set('status')} className="select-brutal">
                    {STATUSES.map(s => <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>)}
                  </select>
                </div>
              </div>
              <div>
                <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Notes</label>
                <textarea data-testid="sponsor-notes-input" value={form.notes} onChange={set('notes')} className="input-brutal h-20 resize-none" placeholder="Sponsor details, deliverables..." />
              </div>
              <button data-testid="submit-sponsor-btn" type="submit" className="btn-accent w-full text-center">
                {editing ? 'Update Sponsor' : 'Add Sponsor'}
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
