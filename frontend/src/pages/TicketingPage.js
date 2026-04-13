import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Ticket, ShoppingCart } from '@phosphor-icons/react';

const PACKAGE_DISPLAY = {
  general: { name: 'General Admission', color: 'border-zinc-400' },
  vip: { name: 'VIP', color: 'border-[#D4AF37]' },
  ringside: { name: 'Ringside', color: 'border-[#DC2626]' },
  ppv: { name: 'Pay-Per-View', color: 'border-blue-500' },
};

export default function TicketingPage() {
  const { api } = useAuth();
  const [events, setEvents] = useState([]);
  const [packages, setPackages] = useState({});
  const [selectedEvent, setSelectedEvent] = useState('');
  const [history, setHistory] = useState([]);
  const [purchasing, setPurchasing] = useState('');

  useEffect(() => {
    api.get('/events').then(r => setEvents(r.data));
    api.get('/tickets/packages').then(r => setPackages(r.data));
    api.get('/tickets/history').then(r => setHistory(r.data));
  }, [api]);

  const purchaseTicket = async (packageId) => {
    if (!selectedEvent) { alert('Please select an event'); return; }
    setPurchasing(packageId);
    try {
      const origin = window.location.origin;
      const { data } = await api.post('/tickets/checkout', {
        event_id: selectedEvent,
        package_id: packageId,
        quantity: 1,
        origin_url: origin
      });
      if (data.url) {
        window.location.href = data.url;
      }
    } catch (e) {
      console.error('Ticket purchase error:', e);
      alert('Failed to create checkout session');
    }
    setPurchasing('');
  };

  const selectedEventData = events.find(e => e._id === selectedEvent);

  return (
    <div data-testid="ticketing-page" className="animate-in">
      <div className="flex items-center gap-4 mb-8">
        <div className="w-12 h-12 bg-[#DC2626] flex items-center justify-center">
          <Ticket weight="fill" className="text-white" size={28} />
        </div>
        <div>
          <h1 className="font-heading text-5xl uppercase leading-none">Ticketing</h1>
          <p className="text-zinc-500">Purchase and manage event tickets</p>
        </div>
      </div>

      {/* Event Selector */}
      <div className="card-brutal p-4 mb-6">
        <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-2 block">Select Event</label>
        <select data-testid="ticket-event-select" value={selectedEvent} onChange={e => setSelectedEvent(e.target.value)} className="select-brutal max-w-md">
          <option value="">-- Choose an event --</option>
          {events.map(ev => (
            <option key={ev._id} value={ev._id}>{ev.title} ({ev.date})</option>
          ))}
        </select>
      </div>

      {selectedEvent && selectedEventData && (
        <>
          {/* Event Info */}
          <div className="accent-panel mb-6">
            <p className="font-mono text-xs uppercase tracking-widest text-zinc-400">{selectedEventData.date}</p>
            <h2 className="font-heading text-3xl uppercase">{selectedEventData.title}</h2>
            <p className="text-zinc-400 text-sm">{selectedEventData.venue}, {selectedEventData.city}</p>
          </div>

          {/* Ticket Packages */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 mb-8">
            {Object.entries(packages).map(([id, pkg]) => (
              <div key={id} data-testid={`ticket-package-${id}`} className={`card-brutal overflow-hidden border-t-4 ${PACKAGE_DISPLAY[id]?.color || 'border-zinc-300'}`}>
                <div className="p-5 text-center">
                  <p className="font-heading text-xl uppercase mb-1">{pkg.name}</p>
                  <p className="stat-value text-[#DC2626]">${pkg.price.toFixed(2)}</p>
                  <button
                    data-testid={`buy-ticket-${id}`}
                    onClick={() => purchaseTicket(id)}
                    disabled={purchasing === id}
                    className="btn-accent w-full text-center mt-4 text-sm flex items-center justify-center gap-2 disabled:opacity-50"
                  >
                    <ShoppingCart size={16} weight="bold" />
                    {purchasing === id ? 'Processing...' : 'Buy Now'}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {/* Purchase History */}
      {history.length > 0 && (
        <div className="card-brutal overflow-hidden">
          <div className="table-header-brutal p-4">
            <span className="text-lg">Purchase History</span>
          </div>
          <div className="divide-y-2 divide-zinc-100">
            {history.map((t, i) => (
              <div key={i} data-testid={`ticket-history-${i}`} className="p-4 flex items-center justify-between">
                <div>
                  <p className="font-semibold">{t.package_name}</p>
                  <p className="text-sm text-zinc-500">{t.created_at ? new Date(t.created_at).toLocaleDateString() : ''}</p>
                </div>
                <div className="text-right">
                  <p className="font-heading text-lg">${(t.amount || 0).toFixed(2)}</p>
                  <span className={`badge-status text-xs ${t.payment_status === 'paid' ? 'border-green-600 text-green-700' : 'border-zinc-400 text-zinc-500'}`}>
                    {t.payment_status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {!selectedEvent && (
        <div className="card-brutal p-16 text-center">
          <Ticket size={48} weight="bold" className="mx-auto mb-4 text-zinc-200" />
          <p className="font-heading text-3xl uppercase text-zinc-300 mb-2">Select an Event</p>
          <p className="text-zinc-500">Choose an event to view available ticket packages</p>
        </div>
      )}
    </div>
  );
}
