import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Plus, Trash, X, PencilSimple, Gavel, Star } from '@phosphor-icons/react';

const ROLES = ['referee', 'judge', 'announcer', 'timekeeper', 'inspector', 'cutman', 'physician'];
const ROLE_COLORS = { referee: 'bg-[#DC2626] text-white', judge: 'bg-zinc-950 text-white', announcer: 'bg-[#D4AF37] text-zinc-950', physician: 'bg-blue-600 text-white', cutman: 'bg-green-600 text-white', timekeeper: 'bg-zinc-500 text-white', inspector: 'bg-purple-600 text-white' };

export default function OfficialsPage() {
  const { api } = useAuth();
  const [officials, setOfficials] = useState([]);
  const [showModal, setShowModal] = useState(false);
  const [editing, setEditing] = useState(null);
  const [filter, setFilter] = useState('all');
  const [form, setForm] = useState({ name: '', role: 'referee', email: '', phone: '', state_licenses: [], rating: 0, status: 'active', notes: '' });

  const load = () => api.get('/officials').then(r => setOfficials(r.data)).catch(console.error);
  useEffect(() => { load(); }, [api]);

  const openCreate = () => { setEditing(null); setForm({ name: '', role: 'referee', email: '', phone: '', state_licenses: [], rating: 0, status: 'active', notes: '' }); setShowModal(true); };
  const openEdit = (o) => { setEditing(o._id); setForm({ name: o.name, role: o.role, email: o.email || '', phone: o.phone || '', state_licenses: o.state_licenses || [], rating: o.rating || 0, status: o.status || 'active', notes: o.notes || '' }); setShowModal(true); };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const payload = { ...form, rating: parseInt(form.rating) || 0 };
    if (editing) await api.put(`/officials/${editing}`, payload);
    else await api.post('/officials', payload);
    setShowModal(false); load();
  };

  const handleDelete = async (id) => { if (window.confirm('Remove?')) { await api.delete(`/officials/${id}`); load(); } };
  const filtered = filter === 'all' ? officials : officials.filter(o => o.role === filter);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  return (
    <div data-testid="officials-page" className="animate-in">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="font-heading text-5xl uppercase leading-none">Officials & Staff</h1>
          <p className="text-zinc-500 mt-1">{officials.length} registered officials</p>
        </div>
        <button data-testid="add-official-btn" onClick={openCreate} className="btn-accent flex items-center gap-2"><Plus size={18} weight="bold" /> Add Official</button>
      </div>
      <div className="flex flex-wrap gap-2 mb-6">
        <button onClick={() => setFilter('all')} className={`font-mono text-xs uppercase px-3 py-1.5 border-2 ${filter === 'all' ? 'bg-zinc-950 text-white border-zinc-950' : 'border-zinc-300 text-zinc-500'}`}>All</button>
        {ROLES.map(r => <button key={r} onClick={() => setFilter(r)} className={`font-mono text-xs uppercase px-3 py-1.5 border-2 ${filter === r ? 'bg-zinc-950 text-white border-zinc-950' : 'border-zinc-300 text-zinc-500'}`}>{r}</button>)}
      </div>
      {filtered.length === 0 ? <div className="card-brutal p-12 text-center"><p className="font-heading text-3xl uppercase text-zinc-300">No Officials</p></div> : (
        <div className="card-brutal overflow-hidden">
          <table className="w-full">
            <thead><tr className="table-header-brutal"><th className="text-left p-4">Name</th><th className="text-left p-4">Role</th><th className="text-center p-4">Rating</th><th className="text-left p-4">Contact</th><th className="text-center p-4">Status</th><th className="text-right p-4">Actions</th></tr></thead>
            <tbody className="divide-y-2 divide-zinc-100">
              {filtered.map(o => (
                <tr key={o._id} data-testid={`official-row-${o._id}`} className="hover:bg-zinc-50">
                  <td className="p-4 font-semibold">{o.name}</td>
                  <td className="p-4"><span className={`font-heading uppercase text-xs px-2 py-1 ${ROLE_COLORS[o.role] || 'bg-zinc-200'}`}>{o.role}</span></td>
                  <td className="p-4 text-center">{[...Array(5)].map((_, i) => <Star key={i} size={14} weight={i < (o.rating || 0) ? "fill" : "regular"} className={i < (o.rating || 0) ? "text-[#D4AF37] inline" : "text-zinc-300 inline"} />)}</td>
                  <td className="p-4 text-sm text-zinc-500">{o.email || o.phone || '-'}</td>
                  <td className="p-4 text-center"><span className={`badge-status text-xs ${o.status === 'active' ? 'border-green-600 text-green-700' : 'border-zinc-400 text-zinc-500'}`}>{o.status}</span></td>
                  <td className="p-4 text-right"><button onClick={() => openEdit(o)} className="p-2 hover:bg-zinc-100"><PencilSimple size={16} weight="bold" /></button><button onClick={() => handleDelete(o._id)} className="p-2 hover:bg-red-50 hover:text-red-600"><Trash size={16} weight="bold" /></button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {showModal && (
        <div className="fixed inset-0 modal-overlay flex items-center justify-center z-50 p-4" onClick={() => setShowModal(false)}>
          <div className="bg-white border-2 border-zinc-950 shadow-[8px_8px_0px_0px_rgba(9,9,11,1)] w-full max-w-lg animate-in" onClick={e => e.stopPropagation()}>
            <div className="bg-zinc-950 text-white p-4 flex items-center justify-between"><h2 className="font-heading text-2xl uppercase">{editing ? 'Edit' : 'Add'} Official</h2><button onClick={() => setShowModal(false)}><X size={20} className="text-white" /></button></div>
            <form onSubmit={handleSubmit} className="p-6 space-y-4">
              <div className="grid grid-cols-2 gap-4"><div><label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Name</label><input data-testid="official-name" value={form.name} onChange={set('name')} className="input-brutal" required /></div><div><label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Role</label><select data-testid="official-role" value={form.role} onChange={set('role')} className="select-brutal">{ROLES.map(r => <option key={r} value={r}>{r.charAt(0).toUpperCase()+r.slice(1)}</option>)}</select></div></div>
              <div className="grid grid-cols-2 gap-4"><div><label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Email</label><input value={form.email} onChange={set('email')} className="input-brutal" /></div><div><label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Phone</label><input value={form.phone} onChange={set('phone')} className="input-brutal" /></div></div>
              <div className="grid grid-cols-2 gap-4"><div><label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Rating (1-5)</label><input type="number" min="0" max="5" value={form.rating} onChange={set('rating')} className="input-brutal" /></div><div><label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Status</label><select value={form.status} onChange={set('status')} className="select-brutal"><option value="active">Active</option><option value="inactive">Inactive</option></select></div></div>
              <div><label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Notes</label><textarea value={form.notes} onChange={set('notes')} className="input-brutal h-16 resize-none" /></div>
              <button data-testid="submit-official-btn" type="submit" className="btn-accent w-full text-center">{editing ? 'Update' : 'Add'} Official</button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
