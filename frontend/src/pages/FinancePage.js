import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Plus, Trash, X, TrendUp, TrendDown } from '@phosphor-icons/react';

const REVENUE_CATEGORIES = ['Ticket Sales', 'Sponsorship', 'PPV Revenue', 'Merchandise', 'Other Revenue'];
const EXPENSE_CATEGORIES = ['Venue Rental', 'Fighter Payouts', 'Staff Wages', 'Marketing', 'Equipment', 'Insurance', 'Travel', 'Catering', 'Production', 'Other Expense'];

export default function FinancePage() {
  const { api } = useAuth();
  const [financials, setFinancials] = useState([]);
  const [events, setEvents] = useState([]);
  const [summary, setSummary] = useState({ total_revenue: 0, total_expenses: 0, net: 0 });
  const [showModal, setShowModal] = useState(false);
  const [selectedEvent, setSelectedEvent] = useState('');
  const [form, setForm] = useState({ event_id: '', type: 'revenue', category: 'Ticket Sales', amount: 0, description: '' });

  const load = () => {
    const query = selectedEvent ? `?event_id=${selectedEvent}` : '';
    api.get(`/financials${query}`).then(r => setFinancials(r.data));
    api.get('/financials/summary').then(r => setSummary(r.data));
    api.get('/events').then(r => setEvents(r.data));
  };
  useEffect(() => { load(); }, [selectedEvent]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const eventId = form.event_id || (events.length > 0 ? events[0]._id : '');
    if (!eventId) { alert('Please select an event'); return; }
    await api.post('/financials', { ...form, event_id: eventId, amount: parseFloat(form.amount) });
    setShowModal(false);
    load();
  };

  const handleDelete = async (id) => {
    await api.delete(`/financials/${id}`);
    load();
  };

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  return (
    <div data-testid="finance-page" className="animate-in">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="font-heading text-5xl uppercase leading-none">Financials</h1>
          <p className="text-zinc-500 mt-1">Track revenue and expenses</p>
        </div>
        <button data-testid="add-financial-btn" onClick={() => { setForm({ event_id: events[0]?._id || '', type: 'revenue', category: 'Ticket Sales', amount: 0, description: '' }); setShowModal(true); }} className="btn-accent flex items-center gap-2">
          <Plus size={18} weight="bold" /> Add Record
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mb-8">
        <div className="card-brutal p-5">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-8 h-8 bg-green-600 flex items-center justify-center"><TrendUp size={16} weight="bold" className="text-white" /></div>
            <span className="font-mono text-xs uppercase tracking-widest text-zinc-500">Total Revenue</span>
          </div>
          <p data-testid="total-revenue" className="stat-value text-green-600">${(summary.total_revenue || 0).toLocaleString()}</p>
        </div>
        <div className="card-brutal p-5">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-8 h-8 bg-red-600 flex items-center justify-center"><TrendDown size={16} weight="bold" className="text-white" /></div>
            <span className="font-mono text-xs uppercase tracking-widest text-zinc-500">Total Expenses</span>
          </div>
          <p data-testid="total-expenses" className="stat-value text-red-600">${(summary.total_expenses || 0).toLocaleString()}</p>
        </div>
        <div className="card-brutal p-5">
          <div className="flex items-center gap-3 mb-2">
            <div className={`w-8 h-8 ${(summary.net || 0) >= 0 ? 'bg-green-600' : 'bg-red-600'} flex items-center justify-center`}>
              {(summary.net || 0) >= 0 ? <TrendUp size={16} weight="bold" className="text-white" /> : <TrendDown size={16} weight="bold" className="text-white" />}
            </div>
            <span className="font-mono text-xs uppercase tracking-widest text-zinc-500">Net Profit</span>
          </div>
          <p data-testid="net-profit" className={`stat-value ${(summary.net || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>${(summary.net || 0).toLocaleString()}</p>
        </div>
      </div>

      {/* Event Filter */}
      <div className="mb-6">
        <select data-testid="finance-event-filter" value={selectedEvent} onChange={e => setSelectedEvent(e.target.value)} className="select-brutal max-w-sm">
          <option value="">All Events</option>
          {events.map(ev => <option key={ev._id} value={ev._id}>{ev.title}</option>)}
        </select>
      </div>

      {/* Transactions Table */}
      {financials.length === 0 ? (
        <div className="card-brutal p-12 text-center">
          <p className="font-heading text-3xl uppercase text-zinc-300 mb-2">No Records</p>
          <p className="text-zinc-500">Add revenue and expense records</p>
        </div>
      ) : (
        <div className="card-brutal overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="table-header-brutal">
                <th className="text-left p-4">Type</th>
                <th className="text-left p-4">Category</th>
                <th className="text-left p-4">Event</th>
                <th className="text-right p-4">Amount</th>
                <th className="text-left p-4">Description</th>
                <th className="text-right p-4">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y-2 divide-zinc-100">
              {financials.map(f => {
                const evName = events.find(e => e._id === f.event_id)?.title || 'N/A';
                return (
                  <tr key={f._id} data-testid={`financial-row-${f._id}`} className="hover:bg-zinc-50 transition-colors">
                    <td className="p-4">
                      <span className={`badge-status text-xs ${f.type === 'revenue' ? 'border-green-600 text-green-700' : 'border-red-600 text-red-700'}`}>
                        {f.type}
                      </span>
                    </td>
                    <td className="p-4 font-medium">{f.category}</td>
                    <td className="p-4 text-sm text-zinc-500">{evName}</td>
                    <td className={`p-4 text-right font-heading text-xl ${f.type === 'revenue' ? 'text-green-600' : 'text-red-600'}`}>
                      {f.type === 'revenue' ? '+' : '-'}${(f.amount || 0).toLocaleString()}
                    </td>
                    <td className="p-4 text-sm text-zinc-500">{f.description || '-'}</td>
                    <td className="p-4 text-right">
                      <button data-testid={`delete-financial-${f._id}`} onClick={() => handleDelete(f._id)} className="p-2 hover:bg-red-50 hover:text-red-600 transition-colors">
                        <Trash size={16} weight="bold" />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 modal-overlay flex items-center justify-center z-50 p-4" onClick={() => setShowModal(false)}>
          <div className="bg-white border-2 border-zinc-950 shadow-[8px_8px_0px_0px_rgba(9,9,11,1)] w-full max-w-lg animate-in" onClick={e => e.stopPropagation()}>
            <div className="bg-zinc-950 text-white p-4 flex items-center justify-between">
              <h2 className="font-heading text-2xl uppercase">Add Financial Record</h2>
              <button data-testid="close-finance-modal" onClick={() => setShowModal(false)}><X size={20} className="text-white" /></button>
            </div>
            <form onSubmit={handleSubmit} className="p-6 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Type</label>
                  <select data-testid="finance-type-select" value={form.type} onChange={e => setForm({ ...form, type: e.target.value, category: e.target.value === 'revenue' ? 'Ticket Sales' : 'Venue Rental' })} className="select-brutal">
                    <option value="revenue">Revenue</option>
                    <option value="expense">Expense</option>
                  </select>
                </div>
                <div>
                  <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Category</label>
                  <select data-testid="finance-category-select" value={form.category} onChange={set('category')} className="select-brutal">
                    {(form.type === 'revenue' ? REVENUE_CATEGORIES : EXPENSE_CATEGORIES).map(c => <option key={c} value={c}>{c}</option>)}
                  </select>
                </div>
              </div>
              <div>
                <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Event</label>
                <select data-testid="finance-event-select" value={form.event_id} onChange={set('event_id')} className="select-brutal" required>
                  <option value="">Select event</option>
                  {events.map(ev => <option key={ev._id} value={ev._id}>{ev.title}</option>)}
                </select>
              </div>
              <div>
                <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Amount ($)</label>
                <input data-testid="finance-amount-input" type="number" step="0.01" value={form.amount} onChange={set('amount')} className="input-brutal" placeholder="10000" required />
              </div>
              <div>
                <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Description</label>
                <input data-testid="finance-desc-input" value={form.description} onChange={set('description')} className="input-brutal" placeholder="VIP section tickets" />
              </div>
              <button data-testid="submit-financial-btn" type="submit" className="btn-accent w-full text-center">Add Record</button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
