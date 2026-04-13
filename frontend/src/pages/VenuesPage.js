import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Plus, Trash, X, PencilSimple, BuildingOffice } from '@phosphor-icons/react';

export default function VenuesPage() {
  const { api } = useAuth();
  const [venues, setVenues] = useState([]);
  const [showModal, setShowModal] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({ name: '', address: '', city: '', state: '', capacity: 0, contact_name: '', contact_email: '', contact_phone: '', rental_cost: 0, specs: {}, status: 'available', notes: '' });

  const load = () => api.get('/venues').then(r => setVenues(r.data)).catch(console.error);
  useEffect(() => { load(); }, [api]);

  const openCreate = () => { setEditing(null); setForm({ name: '', address: '', city: '', state: '', capacity: 0, contact_name: '', contact_email: '', contact_phone: '', rental_cost: 0, specs: {}, status: 'available', notes: '' }); setShowModal(true); };
  const openEdit = (v) => { setEditing(v._id); setForm({ name: v.name, address: v.address || '', city: v.city || '', state: v.state || '', capacity: v.capacity || 0, contact_name: v.contact_name || '', contact_email: v.contact_email || '', contact_phone: v.contact_phone || '', rental_cost: v.rental_cost || 0, specs: v.specs || {}, status: v.status || 'available', notes: v.notes || '' }); setShowModal(true); };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const payload = { ...form, capacity: parseInt(form.capacity), rental_cost: parseFloat(form.rental_cost) };
    if (editing) await api.put(`/venues/${editing}`, payload);
    else await api.post('/venues', payload);
    setShowModal(false); load();
  };

  const handleDelete = async (id) => { if (window.confirm('Remove venue?')) { await api.delete(`/venues/${id}`); load(); } };
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  return (
    <div data-testid="venues-page" className="animate-in">
      <div className="flex items-center justify-between mb-8">
        <div><h1 className="font-heading text-5xl uppercase leading-none">Venues</h1><p className="text-zinc-500 mt-1">{venues.length} venues in database</p></div>
        <button data-testid="add-venue-btn" onClick={openCreate} className="btn-accent flex items-center gap-2"><Plus size={18} weight="bold" /> Add Venue</button>
      </div>
      {venues.length === 0 ? <div className="card-brutal p-12 text-center"><BuildingOffice size={48} className="mx-auto mb-4 text-zinc-200" /><p className="font-heading text-3xl uppercase text-zinc-300">No Venues</p></div> : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
          {venues.map(v => (
            <div key={v._id} data-testid={`venue-card-${v._id}`} className="card-brutal overflow-hidden">
              <div className="bg-zinc-950 text-white p-4">
                <h3 className="font-heading text-xl uppercase">{v.name}</h3>
                <p className="text-zinc-400 text-sm">{v.city}{v.state ? `, ${v.state}` : ''}</p>
              </div>
              <div className="p-4">
                <div className="grid grid-cols-2 gap-3 mb-3">
                  <div><p className="font-mono text-xs text-zinc-400 uppercase">Capacity</p><p className="font-heading text-xl">{(v.capacity || 0).toLocaleString()}</p></div>
                  <div><p className="font-mono text-xs text-zinc-400 uppercase">Rental</p><p className="font-heading text-xl">${(v.rental_cost || 0).toLocaleString()}</p></div>
                </div>
                {v.contact_name && <p className="text-sm text-zinc-500">{v.contact_name} | {v.contact_email}</p>}
                <span className={`badge-status text-xs mt-2 inline-block ${v.status === 'available' ? 'border-green-600 text-green-700' : v.status === 'booked' ? 'border-red-600 text-red-700' : 'border-zinc-400 text-zinc-500'}`}>{v.status}</span>
                <div className="flex gap-2 mt-4">
                  <button onClick={() => openEdit(v)} className="btn-primary text-sm py-2 px-4 flex-1">Edit</button>
                  <button onClick={() => handleDelete(v._id)} className="border-2 border-zinc-950 px-3 py-2 hover:bg-red-50 hover:border-red-500 transition-colors"><Trash size={16} weight="bold" /></button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
      {showModal && (
        <div className="fixed inset-0 modal-overlay flex items-center justify-center z-50 p-4" onClick={() => setShowModal(false)}>
          <div className="bg-white border-2 border-zinc-950 shadow-[8px_8px_0px_0px_rgba(9,9,11,1)] w-full max-w-lg max-h-[90vh] overflow-y-auto animate-in" onClick={e => e.stopPropagation()}>
            <div className="bg-zinc-950 text-white p-4 flex items-center justify-between"><h2 className="font-heading text-2xl uppercase">{editing ? 'Edit' : 'Add'} Venue</h2><button onClick={() => setShowModal(false)}><X size={20} className="text-white" /></button></div>
            <form onSubmit={handleSubmit} className="p-6 space-y-4">
              <div><label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Venue Name</label><input data-testid="venue-name" value={form.name} onChange={set('name')} className="input-brutal" required /></div>
              <div><label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Address</label><input value={form.address} onChange={set('address')} className="input-brutal" /></div>
              <div className="grid grid-cols-2 gap-4"><div><label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">City</label><input value={form.city} onChange={set('city')} className="input-brutal" /></div><div><label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">State</label><input value={form.state} onChange={set('state')} className="input-brutal" /></div></div>
              <div className="grid grid-cols-2 gap-4"><div><label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Capacity</label><input type="number" value={form.capacity} onChange={set('capacity')} className="input-brutal" /></div><div><label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Rental Cost ($)</label><input type="number" value={form.rental_cost} onChange={set('rental_cost')} className="input-brutal" /></div></div>
              <div className="grid grid-cols-2 gap-4"><div><label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Contact Name</label><input value={form.contact_name} onChange={set('contact_name')} className="input-brutal" /></div><div><label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Contact Email</label><input value={form.contact_email} onChange={set('contact_email')} className="input-brutal" /></div></div>
              <div><label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Status</label><select value={form.status} onChange={set('status')} className="select-brutal"><option value="available">Available</option><option value="booked">Booked</option><option value="unavailable">Unavailable</option></select></div>
              <button data-testid="submit-venue-btn" type="submit" className="btn-accent w-full text-center">{editing ? 'Update' : 'Add'} Venue</button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
