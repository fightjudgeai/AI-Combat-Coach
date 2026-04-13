import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Plus, PencilSimple, Trash, X, MapPin } from '@phosphor-icons/react';

const STATUS_OPTIONS = ['planning', 'announced', 'confirmed', 'completed', 'cancelled'];

export default function EventsPage() {
  const { api } = useAuth();
  const [events, setEvents] = useState([]);
  const [showModal, setShowModal] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(emptyForm());

  function emptyForm() {
    return { title: '', date: '', venue: '', city: '', status: 'planning', description: '', budget: 0, ticket_price: 0, capacity: 0 };
  }

  const load = () => api.get('/events').then(r => setEvents(r.data)).catch(console.error);
  useEffect(() => { load(); }, []);

  const openCreate = () => { setEditing(null); setForm(emptyForm()); setShowModal(true); };
  const openEdit = (ev) => { setEditing(ev._id); setForm({ title: ev.title, date: ev.date, venue: ev.venue, city: ev.city || '', status: ev.status, description: ev.description || '', budget: ev.budget || 0, ticket_price: ev.ticket_price || 0, capacity: ev.capacity || 0 }); setShowModal(true); };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (editing) {
      await api.put(`/events/${editing}`, form);
    } else {
      await api.post('/events', form);
    }
    setShowModal(false);
    load();
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this event?')) return;
    await api.delete(`/events/${id}`);
    load();
  };

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const setNum = (k) => (e) => setForm({ ...form, [k]: parseFloat(e.target.value) || 0 });

  return (
    <div data-testid="events-page" className="animate-in">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="font-heading text-5xl uppercase leading-none">Events</h1>
          <p className="text-zinc-500 mt-1">{events.length} total events</p>
        </div>
        <button data-testid="create-event-btn" onClick={openCreate} className="btn-accent flex items-center gap-2">
          <Plus size={18} weight="bold" /> New Event
        </button>
      </div>

      {events.length === 0 ? (
        <div className="card-brutal p-12 text-center">
          <p className="font-heading text-3xl uppercase text-zinc-300 mb-2">No Events Yet</p>
          <p className="text-zinc-500">Create your first combat sports event</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
          {events.map(ev => (
            <div key={ev._id} data-testid={`event-card-${ev._id}`} className="card-brutal overflow-hidden">
              <div className="bg-zinc-950 text-white p-4 flex items-center justify-between">
                <div>
                  <p className="font-mono text-xs uppercase tracking-widest text-zinc-400">
                    {ev.date ? new Date(ev.date).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' }) : 'TBD'}
                  </p>
                  <h3 className="font-heading text-2xl uppercase leading-tight mt-1">{ev.title}</h3>
                </div>
                <span className={`badge-status text-xs ${ev.status === 'confirmed' ? 'border-green-400 text-green-400' : ev.status === 'cancelled' ? 'border-red-400 text-red-400' : 'border-zinc-400 text-zinc-400'}`}>
                  {ev.status}
                </span>
              </div>
              <div className="p-4">
                <div className="flex items-center gap-2 text-sm text-zinc-500 mb-3">
                  <MapPin size={14} weight="bold" />
                  <span>{ev.venue}{ev.city ? `, ${ev.city}` : ''}</span>
                </div>
                {ev.description && <p className="text-sm text-zinc-600 mb-3 line-clamp-2">{ev.description}</p>}
                <div className="grid grid-cols-3 gap-3 text-center border-t-2 border-zinc-100 pt-3">
                  <div>
                    <p className="font-mono text-xs text-zinc-400 uppercase">Budget</p>
                    <p className="font-heading text-lg">${(ev.budget || 0).toLocaleString()}</p>
                  </div>
                  <div>
                    <p className="font-mono text-xs text-zinc-400 uppercase">Tickets</p>
                    <p className="font-heading text-lg">${ev.ticket_price || 0}</p>
                  </div>
                  <div>
                    <p className="font-mono text-xs text-zinc-400 uppercase">Capacity</p>
                    <p className="font-heading text-lg">{(ev.capacity || 0).toLocaleString()}</p>
                  </div>
                </div>
                <div className="flex gap-2 mt-4">
                  <button data-testid={`edit-event-${ev._id}`} onClick={() => openEdit(ev)} className="btn-primary text-sm py-2 px-4 flex-1">Edit</button>
                  <button data-testid={`delete-event-${ev._id}`} onClick={() => handleDelete(ev._id)} className="border-2 border-zinc-950 text-zinc-950 font-heading uppercase px-4 py-2 text-sm hover:bg-red-50 hover:border-red-500 hover:text-red-600 transition-colors">
                    <Trash size={16} weight="bold" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 modal-overlay flex items-center justify-center z-50 p-4" onClick={() => setShowModal(false)}>
          <div className="bg-white border-2 border-zinc-950 shadow-[8px_8px_0px_0px_rgba(9,9,11,1)] w-full max-w-lg max-h-[90vh] overflow-y-auto animate-in" onClick={e => e.stopPropagation()}>
            <div className="bg-zinc-950 text-white p-4 flex items-center justify-between">
              <h2 className="font-heading text-2xl uppercase">{editing ? 'Edit Event' : 'New Event'}</h2>
              <button data-testid="close-event-modal" onClick={() => setShowModal(false)}><X size={20} className="text-white" /></button>
            </div>
            <form onSubmit={handleSubmit} className="p-6 space-y-4">
              <div>
                <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Event Title</label>
                <input data-testid="event-title-input" value={form.title} onChange={set('title')} className="input-brutal" placeholder="FURY FC 12: REDEMPTION" required />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Date</label>
                  <input data-testid="event-date-input" type="date" value={form.date} onChange={set('date')} className="input-brutal" required />
                </div>
                <div>
                  <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Status</label>
                  <select data-testid="event-status-select" value={form.status} onChange={set('status')} className="select-brutal">
                    {STATUS_OPTIONS.map(s => <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>)}
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Venue</label>
                  <input data-testid="event-venue-input" value={form.venue} onChange={set('venue')} className="input-brutal" placeholder="Madison Square Garden" required />
                </div>
                <div>
                  <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">City</label>
                  <input data-testid="event-city-input" value={form.city} onChange={set('city')} className="input-brutal" placeholder="New York" />
                </div>
              </div>
              <div>
                <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Description</label>
                <textarea data-testid="event-desc-input" value={form.description} onChange={set('description')} className="input-brutal h-20 resize-none" placeholder="Event description..." />
              </div>
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Budget ($)</label>
                  <input data-testid="event-budget-input" type="number" value={form.budget} onChange={setNum('budget')} className="input-brutal" />
                </div>
                <div>
                  <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Ticket ($)</label>
                  <input data-testid="event-ticket-input" type="number" value={form.ticket_price} onChange={setNum('ticket_price')} className="input-brutal" />
                </div>
                <div>
                  <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Capacity</label>
                  <input data-testid="event-capacity-input" type="number" value={form.capacity} onChange={setNum('capacity')} className="input-brutal" />
                </div>
              </div>
              <button data-testid="submit-event-btn" type="submit" className="btn-accent w-full text-center">
                {editing ? 'Update Event' : 'Create Event'}
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
