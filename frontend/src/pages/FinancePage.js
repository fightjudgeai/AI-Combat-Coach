import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Plus, Trash, X, TrendUp, TrendDown } from '@phosphor-icons/react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';

const REVENUE_CATEGORIES = ['Ticket Sales', 'Sponsorship', 'PPV Revenue', 'Merchandise', 'Other Revenue'];
const EXPENSE_CATEGORIES = ['Venue Rental', 'Fighter Payouts', 'Staff Wages', 'Marketing', 'Equipment', 'Insurance', 'Travel', 'Catering', 'Production', 'Other Expense'];
const PIE_COLORS = ['#DC2626', '#D4AF37', '#09090B', '#16A34A', '#3B82F6', '#8B5CF6', '#F59E0B', '#EC4899', '#14B8A6', '#6366F1'];

export default function FinancePage() {
  const { api } = useAuth();
  const [financials, setFinancials] = useState([]);
  const [events, setEvents] = useState([]);
  const [summary, setSummary] = useState({ total_revenue: 0, total_expenses: 0, net: 0 });
  const [analytics, setAnalytics] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [selectedEvent, setSelectedEvent] = useState('');
  const [activeTab, setActiveTab] = useState('overview');
  const [form, setForm] = useState({ event_id: '', type: 'revenue', category: 'Ticket Sales', amount: 0, description: '' });

  const load = () => {
    const query = selectedEvent ? `?event_id=${selectedEvent}` : '';
    api.get(`/financials${query}`).then(r => setFinancials(r.data));
    api.get('/financials/summary').then(r => setSummary(r.data));
    api.get('/financials/analytics').then(r => setAnalytics(r.data));
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
          <p className="text-zinc-500 mt-1">Revenue analytics and expense tracking</p>
        </div>
        <button data-testid="add-financial-btn" onClick={() => { setForm({ event_id: events[0]?._id || '', type: 'revenue', category: 'Ticket Sales', amount: 0, description: '' }); setShowModal(true); }} className="btn-accent flex items-center gap-2">
          <Plus size={18} weight="bold" /> Add Record
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mb-6">
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

      {/* Tabs */}
      <div className="flex gap-2 mb-6">
        {['overview', 'by-event', 'transactions'].map(tab => (
          <button key={tab} onClick={() => setActiveTab(tab)} className={`font-heading uppercase text-lg px-4 py-2 border-2 transition-colors ${activeTab === tab ? 'bg-zinc-950 text-white border-zinc-950' : 'border-zinc-300 text-zinc-500 hover:border-zinc-950'}`}>
            {tab === 'overview' ? 'Analytics' : tab === 'by-event' ? 'By Event' : 'Transactions'}
          </button>
        ))}
      </div>

      {/* Analytics Tab */}
      {activeTab === 'overview' && analytics && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Category Breakdown */}
          <div className="card-brutal p-5">
            <h3 className="font-heading text-xl uppercase mb-4">Spending by Category</h3>
            {analytics.by_category?.length > 0 ? (
              <ResponsiveContainer width="100%" height={280}>
                <PieChart>
                  <Pie data={analytics.by_category} dataKey="amount" nameKey="category" cx="50%" cy="50%" outerRadius={100} label={({ category, amount }) => `${category}: $${amount.toLocaleString()}`}>
                    {analytics.by_category.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                  </Pie>
                  <Tooltip formatter={(val) => `$${val.toLocaleString()}`} />
                </PieChart>
              </ResponsiveContainer>
            ) : <p className="text-zinc-400 text-center py-8">No data yet</p>}
          </div>
          {/* Monthly Trend */}
          <div className="card-brutal p-5">
            <h3 className="font-heading text-xl uppercase mb-4">Monthly Revenue vs Expenses</h3>
            {analytics.monthly?.length > 0 ? (
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={analytics.monthly}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E4E4E7" />
                  <XAxis dataKey="month" tick={{ fontFamily: 'JetBrains Mono', fontSize: 11 }} />
                  <YAxis tick={{ fontFamily: 'JetBrains Mono', fontSize: 11 }} />
                  <Tooltip formatter={(val) => `$${val.toLocaleString()}`} />
                  <Bar dataKey="revenue" fill="#16A34A" name="Revenue" />
                  <Bar dataKey="expenses" fill="#DC2626" name="Expenses" />
                </BarChart>
              </ResponsiveContainer>
            ) : <p className="text-zinc-400 text-center py-8">No data yet</p>}
          </div>
        </div>
      )}

      {/* By Event Tab */}
      {activeTab === 'by-event' && analytics && (
        <div className="card-brutal overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="table-header-brutal">
                <th className="text-left p-4">Event</th>
                <th className="text-right p-4">Revenue</th>
                <th className="text-right p-4">Expenses</th>
                <th className="text-right p-4">Net</th>
              </tr>
            </thead>
            <tbody className="divide-y-2 divide-zinc-100">
              {(analytics.by_event || []).map((ev, i) => (
                <tr key={i} className="hover:bg-zinc-50">
                  <td className="p-4 font-medium">{ev.event_name}</td>
                  <td className="p-4 text-right font-heading text-green-600">${(ev.revenue || 0).toLocaleString()}</td>
                  <td className="p-4 text-right font-heading text-red-600">${(ev.expenses || 0).toLocaleString()}</td>
                  <td className={`p-4 text-right font-heading text-lg ${ev.net >= 0 ? 'text-green-600' : 'text-red-600'}`}>${(ev.net || 0).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {(!analytics.by_event || analytics.by_event.length === 0) && (
            <p className="text-zinc-400 text-center py-8">No financial data yet</p>
          )}
        </div>
      )}

      {/* Transactions Tab */}
      {activeTab === 'transactions' && (
        <>
          <div className="mb-4">
            <select data-testid="finance-event-filter" value={selectedEvent} onChange={e => setSelectedEvent(e.target.value)} className="select-brutal max-w-sm">
              <option value="">All Events</option>
              {events.map(ev => <option key={ev._id} value={ev._id}>{ev.title}</option>)}
            </select>
          </div>
          {financials.length === 0 ? (
            <div className="card-brutal p-12 text-center">
              <p className="font-heading text-3xl uppercase text-zinc-300 mb-2">No Records</p>
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
                      <tr key={f._id} className="hover:bg-zinc-50 transition-colors">
                        <td className="p-4">
                          <span className={`badge-status text-xs ${f.type === 'revenue' ? 'border-green-600 text-green-700' : 'border-red-600 text-red-700'}`}>{f.type}</span>
                        </td>
                        <td className="p-4 font-medium">{f.category}</td>
                        <td className="p-4 text-sm text-zinc-500">{evName}</td>
                        <td className={`p-4 text-right font-heading text-xl ${f.type === 'revenue' ? 'text-green-600' : 'text-red-600'}`}>
                          {f.type === 'revenue' ? '+' : '-'}${(f.amount || 0).toLocaleString()}
                        </td>
                        <td className="p-4 text-sm text-zinc-500">{f.description || '-'}</td>
                        <td className="p-4 text-right">
                          <button onClick={() => handleDelete(f._id)} className="p-2 hover:bg-red-50 hover:text-red-600 transition-colors"><Trash size={16} weight="bold" /></button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </>
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
                <input data-testid="finance-amount-input" type="number" step="0.01" value={form.amount} onChange={set('amount')} className="input-brutal" required />
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
