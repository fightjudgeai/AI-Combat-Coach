import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Ticket, ShoppingCart, TrendUp, TrendDown, Lightning, Sparkle, SpinnerGap, ChartLine } from '@phosphor-icons/react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line } from 'recharts';

const PACKAGE_DISPLAY = {
  general: { name: 'General Admission', color: '#52525B', border: 'border-zinc-400', bg: 'bg-zinc-50' },
  vip: { name: 'VIP', color: '#D4AF37', border: 'border-[#D4AF37]', bg: 'bg-yellow-50' },
  ringside: { name: 'Ringside', color: '#DC2626', border: 'border-[#DC2626]', bg: 'bg-red-50' },
  ppv: { name: 'Pay-Per-View', color: '#3B82F6', border: 'border-blue-500', bg: 'bg-blue-50' },
};

export default function TicketingPage() {
  const { api } = useAuth();
  const [events, setEvents] = useState([]);
  const [selectedEvent, setSelectedEvent] = useState('');
  const [dynamicPricing, setDynamicPricing] = useState(null);
  const [salesAnalytics, setSalesAnalytics] = useState(null);
  const [history, setHistory] = useState([]);
  const [purchasing, setPurchasing] = useState('');
  const [activeTab, setActiveTab] = useState('tickets');
  const [aiRec, setAiRec] = useState('');
  const [aiLoading, setAiLoading] = useState(false);

  useEffect(() => {
    api.get('/events').then(r => setEvents(r.data));
    api.get('/tickets/history').then(r => setHistory(r.data));
  }, [api]);

  const loadPricing = useCallback(async () => {
    if (!selectedEvent) { setDynamicPricing(null); setSalesAnalytics(null); return; }
    try {
      const [pricing, analytics] = await Promise.all([
        api.get(`/tickets/dynamic-pricing/${selectedEvent}`),
        api.get(`/tickets/sales-analytics/${selectedEvent}`)
      ]);
      setDynamicPricing(pricing.data);
      setSalesAnalytics(analytics.data);
    } catch (e) { console.error(e); }
  }, [selectedEvent, api]);

  useEffect(() => { loadPricing(); }, [loadPricing]);

  const purchaseTicket = async (packageId) => {
    if (!selectedEvent) return;
    setPurchasing(packageId);
    try {
      const origin = window.location.origin;
      const { data } = await api.post('/tickets/checkout', {
        event_id: selectedEvent,
        package_id: packageId,
        quantity: 1,
        origin_url: origin
      });
      if (data.url) window.location.href = data.url;
    } catch (e) {
      console.error('Ticket purchase error:', e);
      alert('Failed to create checkout session');
    }
    setPurchasing('');
  };

  const getAiRecommendations = async () => {
    if (!selectedEvent) return;
    setAiLoading(true); setAiRec('');
    try {
      const { data } = await api.post(`/ai/pricing-recommendations?event_id=${selectedEvent}`);
      setAiRec(data.recommendations);
    } catch { setAiRec('Failed to generate recommendations.'); }
    setAiLoading(false);
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
          <p className="text-zinc-500">Dynamic pricing powered by AI</p>
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
          {/* Event Banner */}
          <div className="accent-panel mb-6 flex items-center justify-between">
            <div>
              <p className="font-mono text-xs uppercase tracking-widest text-zinc-400">{selectedEventData.date}</p>
              <h2 className="font-heading text-3xl uppercase">{selectedEventData.title}</h2>
              <p className="text-zinc-400 text-sm">{selectedEventData.venue}, {selectedEventData.city}</p>
            </div>
            {salesAnalytics && (
              <div className="text-right">
                <p className="font-heading text-3xl text-white">{salesAnalytics.total_sold}</p>
                <p className="font-mono text-xs text-zinc-400 uppercase">Tickets Sold</p>
                <div className="w-32 bg-zinc-800 h-2 mt-2">
                  <div className="bg-[#DC2626] h-full transition-all" style={{ width: `${Math.min(salesAnalytics.utilization, 100)}%` }} />
                </div>
                <p className="font-mono text-xs text-zinc-500 mt-1">{salesAnalytics.utilization}% of {salesAnalytics.capacity}</p>
              </div>
            )}
          </div>

          {/* Tabs */}
          <div className="flex gap-2 mb-6">
            {[
              { id: 'tickets', label: 'Buy Tickets' },
              { id: 'pricing', label: 'Pricing Intelligence' },
              { id: 'history', label: 'Purchase History' },
            ].map(tab => (
              <button key={tab.id} onClick={() => setActiveTab(tab.id)} className={`font-heading uppercase text-lg px-4 py-2 border-2 transition-colors ${activeTab === tab.id ? 'bg-zinc-950 text-white border-zinc-950' : 'border-zinc-300 text-zinc-500 hover:border-zinc-950'}`}>
                {tab.label}
              </button>
            ))}
          </div>

          {/* Buy Tickets Tab */}
          {activeTab === 'tickets' && dynamicPricing && (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
              {Object.entries(dynamicPricing).map(([id, pkg]) => {
                const display = PACKAGE_DISPLAY[id] || {};
                const surge = pkg.savings_or_surge;
                return (
                  <div key={id} data-testid={`ticket-package-${id}`} className={`card-brutal overflow-hidden border-t-4 ${display.border || 'border-zinc-300'}`}>
                    <div className={`p-5 ${display.bg || ''}`}>
                      <p className="font-heading text-xl uppercase mb-1">{pkg.name}</p>

                      {/* Dynamic Price Display */}
                      <div className="mb-3">
                        <p className="stat-value" style={{ color: display.color }}>${pkg.dynamic_price.toFixed(2)}</p>
                        {pkg.dynamic_price !== pkg.base_price && (
                          <div className="flex items-center gap-2 mt-1">
                            <span className="text-sm text-zinc-400 line-through">${pkg.base_price.toFixed(2)}</span>
                            <span className={`flex items-center gap-1 font-mono text-xs font-bold ${surge > 0 ? 'text-red-600' : 'text-green-600'}`}>
                              {surge > 0 ? <TrendUp size={12} weight="bold" /> : <TrendDown size={12} weight="bold" />}
                              {surge > 0 ? '+' : ''}{surge}%
                            </span>
                          </div>
                        )}
                      </div>

                      {/* Price Factors */}
                      <div className="space-y-1 mb-4 border-t border-zinc-200 pt-3">
                        {Object.entries(pkg.factors || {}).map(([key, factor]) => (
                          <div key={key} className="flex items-center justify-between text-xs">
                            <span className="text-zinc-500 capitalize">{key}</span>
                            <span className={`font-mono ${factor.multiplier > 1 ? 'text-red-500' : factor.multiplier < 1 ? 'text-green-500' : 'text-zinc-400'}`}>
                              {factor.multiplier > 1 ? '+' : ''}{((factor.multiplier - 1) * 100).toFixed(0)}%
                            </span>
                          </div>
                        ))}
                      </div>

                      <button
                        data-testid={`buy-ticket-${id}`}
                        onClick={() => purchaseTicket(id)}
                        disabled={purchasing === id}
                        className="btn-accent w-full text-center text-sm flex items-center justify-center gap-2 disabled:opacity-50"
                      >
                        <ShoppingCart size={16} weight="bold" />
                        {purchasing === id ? 'Processing...' : 'Buy Now'}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Pricing Intelligence Tab */}
          {activeTab === 'pricing' && (
            <div className="space-y-6">
              {/* Pricing Overview */}
              {dynamicPricing && (
                <div className="card-brutal overflow-hidden">
                  <div className="table-header-brutal p-4 flex items-center justify-between">
                    <span className="text-lg flex items-center gap-2"><ChartLine size={18} /> Dynamic Pricing Overview</span>
                    <span className="font-mono text-xs text-zinc-400">Auto-adjusts based on demand</span>
                  </div>
                  <table className="w-full">
                    <thead className="bg-zinc-100">
                      <tr>
                        <th className="text-left p-3 font-mono text-xs uppercase">Package</th>
                        <th className="text-right p-3 font-mono text-xs uppercase">Base Price</th>
                        <th className="text-right p-3 font-mono text-xs uppercase">Dynamic Price</th>
                        <th className="text-center p-3 font-mono text-xs uppercase">Multiplier</th>
                        <th className="text-center p-3 font-mono text-xs uppercase">Scarcity</th>
                        <th className="text-center p-3 font-mono text-xs uppercase">Urgency</th>
                        <th className="text-center p-3 font-mono text-xs uppercase">Velocity</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-100">
                      {Object.entries(dynamicPricing).map(([id, pkg]) => (
                        <tr key={id} className="hover:bg-zinc-50">
                          <td className="p-3 font-semibold">{pkg.name}</td>
                          <td className="p-3 text-right font-mono text-zinc-500">${pkg.base_price.toFixed(2)}</td>
                          <td className="p-3 text-right font-heading text-xl" style={{ color: PACKAGE_DISPLAY[id]?.color }}>
                            ${pkg.dynamic_price.toFixed(2)}
                          </td>
                          <td className="p-3 text-center">
                            <span className={`font-mono text-sm font-bold ${pkg.multiplier > 1 ? 'text-red-600' : pkg.multiplier < 1 ? 'text-green-600' : 'text-zinc-500'}`}>
                              {pkg.multiplier.toFixed(2)}x
                            </span>
                          </td>
                          <td className="p-3 text-center font-mono text-xs">{pkg.factors?.scarcity?.label}</td>
                          <td className="p-3 text-center font-mono text-xs">{pkg.factors?.urgency?.label}</td>
                          <td className="p-3 text-center font-mono text-xs">{pkg.factors?.velocity?.label}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Sales Analytics Charts */}
              {salesAnalytics && (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  <div className="card-brutal p-5">
                    <h3 className="font-heading text-xl uppercase mb-4">Sales by Package</h3>
                    {salesAnalytics.by_package?.length > 0 ? (
                      <ResponsiveContainer width="100%" height={250}>
                        <BarChart data={salesAnalytics.by_package}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#E4E4E7" />
                          <XAxis dataKey="package" tick={{ fontFamily: 'JetBrains Mono', fontSize: 10 }} />
                          <YAxis tick={{ fontFamily: 'JetBrains Mono', fontSize: 11 }} />
                          <Tooltip />
                          <Bar dataKey="count" fill="#DC2626" name="Tickets Sold" />
                        </BarChart>
                      </ResponsiveContainer>
                    ) : (
                      <div className="h-[250px] flex items-center justify-center text-zinc-400">
                        <p>No sales data yet. Revenue will appear here as tickets are sold.</p>
                      </div>
                    )}
                  </div>
                  <div className="card-brutal p-5">
                    <h3 className="font-heading text-xl uppercase mb-4">Daily Sales Trend</h3>
                    {salesAnalytics.daily_sales?.length > 0 ? (
                      <ResponsiveContainer width="100%" height={250}>
                        <LineChart data={salesAnalytics.daily_sales}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#E4E4E7" />
                          <XAxis dataKey="date" tick={{ fontFamily: 'JetBrains Mono', fontSize: 10 }} />
                          <YAxis tick={{ fontFamily: 'JetBrains Mono', fontSize: 11 }} />
                          <Tooltip />
                          <Line type="monotone" dataKey="count" stroke="#D4AF37" strokeWidth={2} name="Tickets" />
                        </LineChart>
                      </ResponsiveContainer>
                    ) : (
                      <div className="h-[250px] flex items-center justify-center text-zinc-400">
                        <p>Sales trend will appear as daily data accumulates.</p>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Revenue Stats */}
              {salesAnalytics && (
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                  <div className="card-brutal p-4 text-center">
                    <p className="font-mono text-xs uppercase text-zinc-500">Total Sold</p>
                    <p className="stat-value">{salesAnalytics.total_sold}</p>
                  </div>
                  <div className="card-brutal p-4 text-center">
                    <p className="font-mono text-xs uppercase text-zinc-500">Revenue</p>
                    <p className="stat-value text-green-600">${(salesAnalytics.total_revenue || 0).toLocaleString()}</p>
                  </div>
                  <div className="card-brutal p-4 text-center">
                    <p className="font-mono text-xs uppercase text-zinc-500">Capacity</p>
                    <p className="stat-value">{salesAnalytics.capacity}</p>
                  </div>
                  <div className="card-brutal p-4 text-center">
                    <p className="font-mono text-xs uppercase text-zinc-500">Utilization</p>
                    <p className="stat-value text-[#DC2626]">{salesAnalytics.utilization}%</p>
                  </div>
                </div>
              )}

              {/* AI Pricing Recommendations */}
              <div className="card-brutal overflow-hidden">
                <div className="bg-zinc-950 p-4 border-l-4 border-l-[#D4AF37] flex items-center justify-between">
                  <div>
                    <h3 className="font-heading text-xl uppercase text-white flex items-center gap-2">
                      <Sparkle weight="fill" className="text-[#D4AF37]" size={18} /> AI Pricing Recommendations
                    </h3>
                    <p className="text-zinc-400 text-sm">AI analyzes your sales data and recommends optimal pricing</p>
                  </div>
                  <button data-testid="get-ai-pricing-btn" onClick={getAiRecommendations} disabled={aiLoading} className="btn-gold text-sm flex items-center gap-2 disabled:opacity-50">
                    {aiLoading ? <><SpinnerGap size={16} className="animate-spin" /> Analyzing...</> : <><Sparkle weight="fill" size={16} /> Get Recommendations</>}
                  </button>
                </div>
                {aiRec && (
                  <div className="p-6 ai-highlight">
                    <pre data-testid="ai-pricing-result" className="whitespace-pre-wrap text-sm leading-relaxed font-body">{aiRec}</pre>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Purchase History Tab */}
          {activeTab === 'history' && (
            <>
              {history.length > 0 ? (
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
              ) : (
                <div className="card-brutal p-12 text-center">
                  <p className="font-heading text-3xl uppercase text-zinc-300 mb-2">No Purchases</p>
                  <p className="text-zinc-500">Your ticket purchases will appear here</p>
                </div>
              )}
            </>
          )}
        </>
      )}

      {!selectedEvent && (
        <div className="card-brutal p-16 text-center">
          <Ticket size={48} weight="bold" className="mx-auto mb-4 text-zinc-200" />
          <p className="font-heading text-3xl uppercase text-zinc-300 mb-2">Select an Event</p>
          <p className="text-zinc-500">Choose an event to view dynamic ticket pricing</p>
        </div>
      )}
    </div>
  );
}
