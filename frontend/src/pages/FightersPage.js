import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Plus, PencilSimple, Trash, X } from '@phosphor-icons/react';

const WEIGHT_CLASSES = ['Strawweight', 'Flyweight', 'Bantamweight', 'Featherweight', 'Lightweight', 'Welterweight', 'Middleweight', 'Light Heavyweight', 'Heavyweight'];
const STANCES = ['orthodox', 'southpaw', 'switch'];

export default function FightersPage() {
  const { api } = useAuth();
  const [fighters, setFighters] = useState([]);
  const [showModal, setShowModal] = useState(false);
  const [editing, setEditing] = useState(null);
  const [filter, setFilter] = useState('all');
  const [form, setForm] = useState(emptyForm());

  function emptyForm() {
    return { name: '', nickname: '', weight_class: 'Welterweight', wins: 0, losses: 0, draws: 0, status: 'active', age: 0, height: '', reach: '', stance: 'orthodox', gym: '' };
  }

  const load = () => api.get('/fighters').then(r => setFighters(r.data)).catch(console.error);
  useEffect(() => { load(); }, []);

  const openCreate = () => { setEditing(null); setForm(emptyForm()); setShowModal(true); };
  const openEdit = (f) => {
    setEditing(f._id);
    setForm({ name: f.name, nickname: f.nickname || '', weight_class: f.weight_class, wins: f.wins || 0, losses: f.losses || 0, draws: f.draws || 0, status: f.status || 'active', age: f.age || 0, height: f.height || '', reach: f.reach || '', stance: f.stance || 'orthodox', gym: f.gym || '' });
    setShowModal(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const payload = { ...form, wins: parseInt(form.wins), losses: parseInt(form.losses), draws: parseInt(form.draws), age: parseInt(form.age) };
    if (editing) await api.put(`/fighters/${editing}`, payload);
    else await api.post('/fighters', payload);
    setShowModal(false);
    load();
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Remove this fighter?')) return;
    await api.delete(`/fighters/${id}`);
    load();
  };

  const filtered = filter === 'all' ? fighters : fighters.filter(f => f.weight_class === filter);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  return (
    <div data-testid="fighters-page" className="animate-in">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="font-heading text-5xl uppercase leading-none">Fighter Roster</h1>
          <p className="text-zinc-500 mt-1">{fighters.length} fighters registered</p>
        </div>
        <button data-testid="add-fighter-btn" onClick={openCreate} className="btn-accent flex items-center gap-2">
          <Plus size={18} weight="bold" /> Add Fighter
        </button>
      </div>

      {/* Weight Class Filter */}
      <div className="flex flex-wrap gap-2 mb-6">
        <button onClick={() => setFilter('all')} className={`font-mono text-xs uppercase px-3 py-1.5 border-2 transition-colors ${filter === 'all' ? 'bg-zinc-950 text-white border-zinc-950' : 'border-zinc-300 text-zinc-500 hover:border-zinc-950'}`}>
          All
        </button>
        {WEIGHT_CLASSES.map(wc => (
          <button key={wc} onClick={() => setFilter(wc)} className={`font-mono text-xs uppercase px-3 py-1.5 border-2 transition-colors ${filter === wc ? 'bg-zinc-950 text-white border-zinc-950' : 'border-zinc-300 text-zinc-500 hover:border-zinc-950'}`}>
            {wc}
          </button>
        ))}
      </div>

      {/* Fighters Table */}
      {filtered.length === 0 ? (
        <div className="card-brutal p-12 text-center">
          <p className="font-heading text-3xl uppercase text-zinc-300 mb-2">No Fighters</p>
          <p className="text-zinc-500">Add fighters to your roster</p>
        </div>
      ) : (
        <div className="card-brutal overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="table-header-brutal">
                <th className="text-left p-4">Fighter</th>
                <th className="text-left p-4">Weight Class</th>
                <th className="text-center p-4">Record</th>
                <th className="text-center p-4">Age</th>
                <th className="text-center p-4">Status</th>
                <th className="text-right p-4">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y-2 divide-zinc-100">
              {filtered.map(f => (
                <tr key={f._id} data-testid={`fighter-row-${f._id}`} className="hover:bg-zinc-50 transition-colors">
                  <td className="p-4">
                    <div>
                      <p className="font-semibold">{f.name}</p>
                      {f.nickname && <p className="text-sm text-zinc-500">"{f.nickname}"</p>}
                    </div>
                  </td>
                  <td className="p-4"><span className="badge-weight">{f.weight_class}</span></td>
                  <td className="p-4 text-center">
                    <span className="font-heading text-xl">
                      <span className="text-green-600">{f.wins}</span>
                      <span className="text-zinc-300">-</span>
                      <span className="text-red-600">{f.losses}</span>
                      <span className="text-zinc-300">-</span>
                      <span className="text-zinc-500">{f.draws}</span>
                    </span>
                  </td>
                  <td className="p-4 text-center font-mono text-sm">{f.age || '-'}</td>
                  <td className="p-4 text-center">
                    <span className={`badge-status text-xs ${f.status === 'active' ? 'border-green-600 text-green-700' : 'border-zinc-400 text-zinc-500'}`}>
                      {f.status}
                    </span>
                  </td>
                  <td className="p-4 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <button data-testid={`edit-fighter-${f._id}`} onClick={() => openEdit(f)} className="p-2 hover:bg-zinc-100 transition-colors"><PencilSimple size={16} weight="bold" /></button>
                      <button data-testid={`delete-fighter-${f._id}`} onClick={() => handleDelete(f._id)} className="p-2 hover:bg-red-50 hover:text-red-600 transition-colors"><Trash size={16} weight="bold" /></button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 modal-overlay flex items-center justify-center z-50 p-4" onClick={() => setShowModal(false)}>
          <div className="bg-white border-2 border-zinc-950 shadow-[8px_8px_0px_0px_rgba(9,9,11,1)] w-full max-w-lg max-h-[90vh] overflow-y-auto animate-in" onClick={e => e.stopPropagation()}>
            <div className="bg-zinc-950 text-white p-4 flex items-center justify-between">
              <h2 className="font-heading text-2xl uppercase">{editing ? 'Edit Fighter' : 'Add Fighter'}</h2>
              <button data-testid="close-fighter-modal" onClick={() => setShowModal(false)}><X size={20} className="text-white" /></button>
            </div>
            <form onSubmit={handleSubmit} className="p-6 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Full Name</label>
                  <input data-testid="fighter-name-input" value={form.name} onChange={set('name')} className="input-brutal" placeholder="Marcus Johnson" required />
                </div>
                <div>
                  <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Nickname</label>
                  <input data-testid="fighter-nickname-input" value={form.nickname} onChange={set('nickname')} className="input-brutal" placeholder="The Hammer" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Weight Class</label>
                  <select data-testid="fighter-weight-select" value={form.weight_class} onChange={set('weight_class')} className="select-brutal">
                    {WEIGHT_CLASSES.map(wc => <option key={wc} value={wc}>{wc}</option>)}
                  </select>
                </div>
                <div>
                  <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Stance</label>
                  <select data-testid="fighter-stance-select" value={form.stance} onChange={set('stance')} className="select-brutal">
                    {STANCES.map(s => <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>)}
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Wins</label>
                  <input data-testid="fighter-wins-input" type="number" value={form.wins} onChange={set('wins')} className="input-brutal" min="0" />
                </div>
                <div>
                  <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Losses</label>
                  <input data-testid="fighter-losses-input" type="number" value={form.losses} onChange={set('losses')} className="input-brutal" min="0" />
                </div>
                <div>
                  <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Draws</label>
                  <input data-testid="fighter-draws-input" type="number" value={form.draws} onChange={set('draws')} className="input-brutal" min="0" />
                </div>
              </div>
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Age</label>
                  <input data-testid="fighter-age-input" type="number" value={form.age} onChange={set('age')} className="input-brutal" min="0" />
                </div>
                <div>
                  <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Height</label>
                  <input data-testid="fighter-height-input" value={form.height} onChange={set('height')} className="input-brutal" placeholder="5'11&quot;" />
                </div>
                <div>
                  <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Reach</label>
                  <input data-testid="fighter-reach-input" value={form.reach} onChange={set('reach')} className="input-brutal" placeholder="74&quot;" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Gym</label>
                  <input data-testid="fighter-gym-input" value={form.gym} onChange={set('gym')} className="input-brutal" placeholder="Iron Forge MMA" />
                </div>
                <div>
                  <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Status</label>
                  <select data-testid="fighter-status-select" value={form.status} onChange={set('status')} className="select-brutal">
                    <option value="active">Active</option>
                    <option value="inactive">Inactive</option>
                    <option value="injured">Injured</option>
                    <option value="retired">Retired</option>
                  </select>
                </div>
              </div>
              <button data-testid="submit-fighter-btn" type="submit" className="btn-accent w-full text-center">
                {editing ? 'Update Fighter' : 'Add to Roster'}
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
