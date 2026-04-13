import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Plus, Trash, X } from '@phosphor-icons/react';

export default function FightCardPage() {
  const { api } = useAuth();
  const [events, setEvents] = useState([]);
  const [fighters, setFighters] = useState([]);
  const [bouts, setBouts] = useState([]);
  const [selectedEvent, setSelectedEvent] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState({ fighter1_id: '', fighter2_id: '', weight_class: 'Welterweight', rounds: 3, is_main_event: false, bout_order: 0 });

  const WEIGHT_CLASSES = ['Strawweight', 'Flyweight', 'Bantamweight', 'Featherweight', 'Lightweight', 'Welterweight', 'Middleweight', 'Light Heavyweight', 'Heavyweight'];

  useEffect(() => {
    api.get('/events').then(r => setEvents(r.data));
    api.get('/fighters').then(r => setFighters(r.data));
  }, [api]);

  useEffect(() => {
    if (selectedEvent) {
      api.get(`/bouts?event_id=${selectedEvent}`).then(r => setBouts(r.data));
    } else {
      setBouts([]);
    }
  }, [selectedEvent, api]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (form.fighter1_id === form.fighter2_id) { alert('Select two different fighters'); return; }
    await api.post('/bouts', { ...form, event_id: selectedEvent, rounds: parseInt(form.rounds), bout_order: parseInt(form.bout_order) });
    setShowModal(false);
    api.get(`/bouts?event_id=${selectedEvent}`).then(r => setBouts(r.data));
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Remove this bout?')) return;
    await api.delete(`/bouts/${id}`);
    api.get(`/bouts?event_id=${selectedEvent}`).then(r => setBouts(r.data));
  };

  const selectedEventData = events.find(e => e._id === selectedEvent);

  return (
    <div data-testid="fight-card-page" className="animate-in">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="font-heading text-5xl uppercase leading-none">Fight Cards</h1>
          <p className="text-zinc-500 mt-1">Build your event fight cards</p>
        </div>
      </div>

      {/* Event Selector */}
      <div className="card-brutal p-4 mb-6">
        <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-2 block">Select Event</label>
        <select
          data-testid="fight-card-event-select"
          value={selectedEvent}
          onChange={e => setSelectedEvent(e.target.value)}
          className="select-brutal max-w-md"
        >
          <option value="">-- Choose an event --</option>
          {events.map(ev => (
            <option key={ev._id} value={ev._id}>{ev.title} ({ev.date})</option>
          ))}
        </select>
      </div>

      {selectedEvent && (
        <>
          {/* Event Header */}
          <div className="accent-panel mb-6 flex items-center justify-between">
            <div>
              <p className="font-mono text-xs uppercase tracking-widest text-zinc-400">{selectedEventData?.date}</p>
              <h2 className="font-heading text-3xl uppercase">{selectedEventData?.title}</h2>
              <p className="text-zinc-400 text-sm">{selectedEventData?.venue}</p>
            </div>
            <button data-testid="add-bout-btn" onClick={() => { setForm({ fighter1_id: '', fighter2_id: '', weight_class: 'Welterweight', rounds: 3, is_main_event: false, bout_order: bouts.length + 1 }); setShowModal(true); }} className="btn-accent">
              <Plus size={18} weight="bold" className="inline mr-2" /> Add Bout
            </button>
          </div>

          {/* Bouts List */}
          {bouts.length === 0 ? (
            <div className="card-brutal p-12 text-center">
              <p className="font-heading text-3xl uppercase text-zinc-300 mb-2">No Bouts Yet</p>
              <p className="text-zinc-500">Add matchups to build your fight card</p>
            </div>
          ) : (
            <div className="space-y-4">
              {bouts.map((bout, i) => (
                <div key={bout._id} data-testid={`bout-card-${bout._id}`} className="card-brutal overflow-hidden">
                  <div className="flex items-center">
                    {/* Bout Order / Main Event */}
                    <div className={`w-16 h-full flex flex-col items-center justify-center p-4 ${bout.is_main_event ? 'bg-[#D4AF37]' : 'bg-zinc-100'}`}>
                      <span className={`font-heading text-2xl ${bout.is_main_event ? 'text-zinc-950' : 'text-zinc-400'}`}>
                        {bout.is_main_event ? 'ME' : `#${bout.bout_order || i + 1}`}
                      </span>
                    </div>

                    {/* Fighter 1 */}
                    <div className="flex-1 p-4 text-right">
                      <p className="font-semibold text-lg">{bout.fighter1_name || 'TBD'}</p>
                      {bout.fighter1_nickname && <p className="text-sm text-zinc-500">"{bout.fighter1_nickname}"</p>}
                      <p className="font-mono text-sm text-zinc-400">{bout.fighter1_record || '0-0-0'}</p>
                    </div>

                    {/* VS */}
                    <div className="vs-badge flex-shrink-0 mx-2">VS</div>

                    {/* Fighter 2 */}
                    <div className="flex-1 p-4">
                      <p className="font-semibold text-lg">{bout.fighter2_name || 'TBD'}</p>
                      {bout.fighter2_nickname && <p className="text-sm text-zinc-500">"{bout.fighter2_nickname}"</p>}
                      <p className="font-mono text-sm text-zinc-400">{bout.fighter2_record || '0-0-0'}</p>
                    </div>

                    {/* Info */}
                    <div className="px-4 text-center border-l-2 border-zinc-100">
                      <span className="badge-weight">{bout.weight_class}</span>
                      <p className="font-mono text-xs text-zinc-400 mt-1">{bout.rounds} RDS</p>
                    </div>

                    {/* Delete */}
                    <div className="px-4">
                      <button data-testid={`delete-bout-${bout._id}`} onClick={() => handleDelete(bout._id)} className="p-2 hover:bg-red-50 hover:text-red-600 transition-colors">
                        <Trash size={16} weight="bold" />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {/* Add Bout Modal */}
      {showModal && (
        <div className="fixed inset-0 modal-overlay flex items-center justify-center z-50 p-4" onClick={() => setShowModal(false)}>
          <div className="bg-white border-2 border-zinc-950 shadow-[8px_8px_0px_0px_rgba(9,9,11,1)] w-full max-w-lg animate-in" onClick={e => e.stopPropagation()}>
            <div className="bg-zinc-950 text-white p-4 flex items-center justify-between">
              <h2 className="font-heading text-2xl uppercase">Add Bout</h2>
              <button data-testid="close-bout-modal" onClick={() => setShowModal(false)}><X size={20} className="text-white" /></button>
            </div>
            <form onSubmit={handleSubmit} className="p-6 space-y-4">
              <div>
                <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Fighter 1 (Red Corner)</label>
                <select data-testid="bout-fighter1-select" value={form.fighter1_id} onChange={e => setForm({ ...form, fighter1_id: e.target.value })} className="select-brutal" required>
                  <option value="">Select fighter</option>
                  {fighters.map(f => <option key={f._id} value={f._id}>{f.name} ({f.weight_class}) [{f.wins}-{f.losses}-{f.draws}]</option>)}
                </select>
              </div>
              <div>
                <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Fighter 2 (Blue Corner)</label>
                <select data-testid="bout-fighter2-select" value={form.fighter2_id} onChange={e => setForm({ ...form, fighter2_id: e.target.value })} className="select-brutal" required>
                  <option value="">Select fighter</option>
                  {fighters.map(f => <option key={f._id} value={f._id}>{f.name} ({f.weight_class}) [{f.wins}-{f.losses}-{f.draws}]</option>)}
                </select>
              </div>
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Weight Class</label>
                  <select data-testid="bout-weight-select" value={form.weight_class} onChange={e => setForm({ ...form, weight_class: e.target.value })} className="select-brutal">
                    {WEIGHT_CLASSES.map(wc => <option key={wc} value={wc}>{wc}</option>)}
                  </select>
                </div>
                <div>
                  <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Rounds</label>
                  <select data-testid="bout-rounds-select" value={form.rounds} onChange={e => setForm({ ...form, rounds: e.target.value })} className="select-brutal">
                    <option value={3}>3</option>
                    <option value={5}>5</option>
                  </select>
                </div>
                <div>
                  <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Order</label>
                  <input data-testid="bout-order-input" type="number" value={form.bout_order} onChange={e => setForm({ ...form, bout_order: e.target.value })} className="input-brutal" min="1" />
                </div>
              </div>
              <label className="flex items-center gap-3 cursor-pointer">
                <input data-testid="bout-main-event-check" type="checkbox" checked={form.is_main_event} onChange={e => setForm({ ...form, is_main_event: e.target.checked })} className="w-5 h-5 accent-[#DC2626]" />
                <span className="font-heading uppercase text-lg">Main Event</span>
              </label>
              <button data-testid="submit-bout-btn" type="submit" className="btn-accent w-full text-center">Add to Card</button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
