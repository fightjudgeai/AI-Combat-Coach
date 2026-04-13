import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Broadcast, Circle, CheckCircle, Clock, Play, Trophy, CurrencyDollar, Ticket as TicketIcon, ListChecks } from '@phosphor-icons/react';

const BOUT_STATUSES = ['scheduled', 'in_progress', 'completed', 'cancelled'];

export default function FightNightLivePage() {
  const { api } = useAuth();
  const [events, setEvents] = useState([]);
  const [selectedEvent, setSelectedEvent] = useState('');
  const [liveData, setLiveData] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.get('/events').then(r => setEvents(r.data));
  }, [api]);

  const loadLive = useCallback(async () => {
    if (!selectedEvent) return;
    setLoading(true);
    try {
      const { data } = await api.get(`/live/${selectedEvent}`);
      setLiveData(data);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, [selectedEvent, api]);

  useEffect(() => { loadLive(); }, [loadLive]);

  // Auto-refresh every 10 seconds
  useEffect(() => {
    if (!selectedEvent) return;
    const interval = setInterval(loadLive, 10000);
    return () => clearInterval(interval);
  }, [selectedEvent, loadLive]);

  const updateBoutStatus = async (boutId, status) => {
    await api.patch(`/bouts/${boutId}/status`, { status });
    loadLive();
  };

  return (
    <div data-testid="fight-night-live-page" className="animate-in">
      <div className="flex items-center gap-4 mb-8">
        <div className="w-12 h-12 bg-[#DC2626] flex items-center justify-center">
          <Broadcast weight="fill" className="text-white" size={28} />
        </div>
        <div>
          <h1 className="font-heading text-5xl uppercase leading-none">Fight Night Live</h1>
          <p className="text-zinc-500">Real-time event command center</p>
        </div>
        {selectedEvent && (
          <div className="ml-auto flex items-center gap-2">
            <div className="w-3 h-3 bg-[#DC2626] rounded-full animate-pulse" />
            <span className="font-mono text-xs uppercase tracking-widest text-[#DC2626]">Live</span>
          </div>
        )}
      </div>

      {/* Event Selector */}
      <div className="card-brutal p-4 mb-6">
        <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-2 block">Select Event</label>
        <select data-testid="live-event-select" value={selectedEvent} onChange={e => setSelectedEvent(e.target.value)} className="select-brutal max-w-md">
          <option value="">-- Choose an event --</option>
          {events.filter(e => e.status !== 'cancelled').map(ev => (
            <option key={ev._id} value={ev._id}>{ev.title} ({ev.date})</option>
          ))}
        </select>
      </div>

      {loading && !liveData && (
        <div className="flex items-center justify-center h-64">
          <div className="w-8 h-8 bg-[#DC2626] animate-pulse" />
        </div>
      )}

      {liveData && (
        <div className="space-y-6">
          {/* Event Header Banner */}
          <div className="bg-zinc-950 text-white p-6 border-l-4 border-l-[#DC2626]">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-mono text-xs uppercase tracking-widest text-zinc-400">{liveData.event?.date} | {liveData.event?.venue}, {liveData.event?.city}</p>
                <h2 className="font-heading text-4xl uppercase mt-1">{liveData.event?.title}</h2>
              </div>
              <div className="text-right">
                <span className={`badge-status text-sm ${liveData.event?.status === 'confirmed' ? 'border-green-400 text-green-400' : 'border-zinc-400 text-zinc-400'}`}>
                  {liveData.event?.status}
                </span>
              </div>
            </div>
          </div>

          {/* Live Stats Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div data-testid="live-stat-bouts" className="card-brutal p-4 text-center">
              <Trophy size={24} weight="bold" className="mx-auto mb-2 text-[#D4AF37]" />
              <p className="stat-value">{liveData.completed_bouts}/{liveData.total_bouts}</p>
              <p className="font-mono text-xs uppercase text-zinc-500">Bouts Complete</p>
            </div>
            <div data-testid="live-stat-tickets" className="card-brutal p-4 text-center">
              <TicketIcon size={24} weight="bold" className="mx-auto mb-2 text-[#DC2626]" />
              <p className="stat-value">{liveData.tickets_sold}</p>
              <p className="font-mono text-xs uppercase text-zinc-500">Tickets Sold</p>
            </div>
            <div data-testid="live-stat-revenue" className="card-brutal p-4 text-center">
              <CurrencyDollar size={24} weight="bold" className="mx-auto mb-2 text-green-600" />
              <p className="stat-value text-green-600">${(liveData.financial?.revenue || 0).toLocaleString()}</p>
              <p className="font-mono text-xs uppercase text-zinc-500">Revenue</p>
            </div>
            <div data-testid="live-stat-tasks" className="card-brutal p-4 text-center">
              <ListChecks size={24} weight="bold" className="mx-auto mb-2 text-zinc-600" />
              <p className="stat-value">{liveData.tasks?.filter(t => t.status === 'completed').length}/{liveData.tasks?.length || 0}</p>
              <p className="font-mono text-xs uppercase text-zinc-500">Tasks Done</p>
            </div>
          </div>

          {/* Current Bout Highlight */}
          {liveData.current_bout && (
            <div className="bg-[#DC2626] text-white p-6 border-2 border-zinc-950 shadow-[6px_6px_0px_0px_rgba(9,9,11,1)]">
              <p className="font-mono text-xs uppercase tracking-widest text-red-200 mb-2">Now Fighting</p>
              <div className="flex items-center justify-center gap-6">
                <div className="text-right flex-1">
                  <p className="font-heading text-3xl">{liveData.current_bout.fighter1_name || 'TBD'}</p>
                  <p className="font-mono text-sm text-red-200">{liveData.current_bout.fighter1_record}</p>
                </div>
                <div className="vs-badge bg-white text-[#DC2626] text-2xl font-heading w-14 h-14 flex items-center justify-center">VS</div>
                <div className="text-left flex-1">
                  <p className="font-heading text-3xl">{liveData.current_bout.fighter2_name || 'TBD'}</p>
                  <p className="font-mono text-sm text-red-200">{liveData.current_bout.fighter2_record}</p>
                </div>
              </div>
              <div className="text-center mt-3">
                <span className="badge-weight bg-red-800 text-white">{liveData.current_bout.weight_class}</span>
                <span className="font-mono text-xs ml-3 text-red-200">{liveData.current_bout.rounds} Rounds</span>
              </div>
            </div>
          )}

          {/* Fight Card with Status Controls */}
          <div className="card-brutal overflow-hidden">
            <div className="table-header-brutal p-4">
              <span className="text-lg">Fight Card</span>
            </div>
            {liveData.bouts?.length === 0 ? (
              <div className="p-8 text-center text-zinc-400">No bouts scheduled for this event</div>
            ) : (
              <div className="divide-y-2 divide-zinc-100">
                {liveData.bouts?.map((bout, i) => (
                  <div key={bout._id} data-testid={`live-bout-${bout._id}`} className={`p-4 flex items-center gap-4 ${bout.status === 'in_progress' ? 'bg-red-50' : bout.status === 'completed' ? 'bg-green-50' : ''}`}>
                    <div className={`w-10 text-center ${bout.is_main_event ? 'text-[#D4AF37]' : 'text-zinc-400'}`}>
                      <span className="font-heading text-lg">{bout.is_main_event ? 'ME' : `#${bout.bout_order || i + 1}`}</span>
                    </div>
                    <div className="flex-1 flex items-center gap-3">
                      <span className="font-semibold">{bout.fighter1_name || 'TBD'}</span>
                      <span className="vs-badge w-8 h-8 text-sm">VS</span>
                      <span className="font-semibold">{bout.fighter2_name || 'TBD'}</span>
                      <span className="badge-weight ml-2">{bout.weight_class}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      {bout.status === 'scheduled' && (
                        <button data-testid={`start-bout-${bout._id}`} onClick={() => updateBoutStatus(bout._id, 'in_progress')} className="flex items-center gap-1 px-3 py-1.5 bg-[#DC2626] text-white font-heading uppercase text-sm hover:bg-red-700 transition-colors">
                          <Play size={14} weight="fill" /> Start
                        </button>
                      )}
                      {bout.status === 'in_progress' && (
                        <button data-testid={`end-bout-${bout._id}`} onClick={() => updateBoutStatus(bout._id, 'completed')} className="flex items-center gap-1 px-3 py-1.5 bg-green-600 text-white font-heading uppercase text-sm hover:bg-green-700 transition-colors">
                          <CheckCircle size={14} weight="fill" /> End
                        </button>
                      )}
                      <span className={`flex items-center gap-1 font-mono text-xs uppercase ${bout.status === 'in_progress' ? 'text-[#DC2626]' : bout.status === 'completed' ? 'text-green-600' : 'text-zinc-400'}`}>
                        {bout.status === 'in_progress' ? <><div className="w-2 h-2 bg-[#DC2626] rounded-full animate-pulse" /> Live</> : bout.status === 'completed' ? <><CheckCircle size={12} weight="fill" /> Done</> : <><Clock size={12} /> Upcoming</>}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Financial Running Tally */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="accent-panel">
              <p className="font-mono text-xs uppercase tracking-widest text-zinc-400">Revenue</p>
              <p className="font-heading text-3xl text-green-400 mt-1">${(liveData.financial?.revenue || 0).toLocaleString()}</p>
            </div>
            <div className="accent-panel">
              <p className="font-mono text-xs uppercase tracking-widest text-zinc-400">Expenses</p>
              <p className="font-heading text-3xl text-red-400 mt-1">${(liveData.financial?.expenses || 0).toLocaleString()}</p>
            </div>
            <div className="accent-panel border-l-[#D4AF37]">
              <p className="font-mono text-xs uppercase tracking-widest text-zinc-400">Net Profit</p>
              <p className={`font-heading text-3xl mt-1 ${(liveData.financial?.net || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                ${(liveData.financial?.net || 0).toLocaleString()}
              </p>
            </div>
          </div>
        </div>
      )}

      {!selectedEvent && (
        <div className="card-brutal p-16 text-center">
          <Broadcast size={48} weight="bold" className="mx-auto mb-4 text-zinc-200" />
          <p className="font-heading text-3xl uppercase text-zinc-300 mb-2">Select an Event</p>
          <p className="text-zinc-500">Choose an event above to enter the live command center</p>
        </div>
      )}
    </div>
  );
}
