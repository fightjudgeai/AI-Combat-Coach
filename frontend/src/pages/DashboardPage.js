import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import {
  CalendarBlank, UsersFour, Trophy, ListChecks,
  CurrencyDollar, TrendUp, ArrowRight, Handshake, Ticket
} from '@phosphor-icons/react';
import { useNavigate } from 'react-router-dom';

export default function DashboardPage() {
  const { api, user } = useAuth();
  const [stats, setStats] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    api.get('/dashboard/stats').then(r => setStats(r.data)).catch(console.error);
  }, [api]);

  if (!stats) return <div className="flex items-center justify-center h-64"><div className="w-8 h-8 bg-[#DC2626] animate-pulse" /></div>;

  const statCards = [
    { label: 'Total Events', value: stats.total_events, icon: CalendarBlank, color: '#DC2626', link: '/events' },
    { label: 'Active Fighters', value: stats.total_fighters, icon: UsersFour, color: '#09090B', link: '/fighters' },
    { label: 'Upcoming Events', value: stats.upcoming_events, icon: Trophy, color: '#D4AF37', link: '/events' },
    { label: 'Pending Tasks', value: stats.tasks_pending, icon: ListChecks, color: '#DC2626', link: '/tasks' },
    { label: 'Sponsors', value: stats.sponsors_count || 0, icon: Handshake, color: '#D4AF37', link: '/sponsors' },
    { label: 'Tickets Sold', value: stats.tickets_sold || 0, icon: Ticket, color: '#3B82F6', link: '/tickets' },
    { label: 'Total Revenue', value: `$${(stats.total_revenue || 0).toLocaleString()}`, icon: CurrencyDollar, color: '#16A34A', link: '/finance' },
    { label: 'Net Profit', value: `$${(stats.net_profit || 0).toLocaleString()}`, icon: TrendUp, color: stats.net_profit >= 0 ? '#16A34A' : '#DC2626', link: '/finance' },
  ];

  return (
    <div data-testid="dashboard-page" className="animate-in">
      <div className="mb-8">
        <h1 className="font-heading text-5xl uppercase leading-none">Command Center</h1>
        <p className="text-zinc-500 mt-1">Welcome back, {user?.name || 'Promoter'}</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 mb-8">
        {statCards.map((card, i) => (
          <div key={i} data-testid={`stat-${card.label.toLowerCase().replace(/\s/g, '-')}`} onClick={() => navigate(card.link)} className="card-brutal p-5 cursor-pointer" style={{ animationDelay: `${i * 50}ms` }}>
            <div className="flex items-start justify-between">
              <div>
                <p className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-2">{card.label}</p>
                <p className="stat-value" style={{ color: card.color }}>{card.value}</p>
              </div>
              <div className="w-10 h-10 flex items-center justify-center" style={{ background: card.color }}>
                <card.icon size={20} weight="bold" className="text-white" />
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mb-8">
        <button data-testid="quick-live" onClick={() => navigate('/live')} className="accent-panel hover:-translate-y-1 transition-transform cursor-pointer text-left">
          <p className="font-heading text-xl uppercase">Fight Night Live</p>
          <p className="text-zinc-400 text-sm mt-1">Open real-time event command center</p>
        </button>
        <button data-testid="quick-checklists" onClick={() => navigate('/checklists')} className="bg-[#D4AF37] text-zinc-950 p-6 border-2 border-zinc-950 shadow-[4px_4px_0px_0px_rgba(9,9,11,1)] hover:-translate-y-1 transition-transform cursor-pointer text-left">
          <p className="font-heading text-xl uppercase">Checklists</p>
          <p className="text-sm mt-1 opacity-80">Apply pre-built operational checklists</p>
        </button>
        <button data-testid="quick-ai" onClick={() => navigate('/ai-tools')} className="bg-white border-2 border-zinc-950 shadow-[4px_4px_0px_0px_rgba(9,9,11,1)] p-6 hover:-translate-y-1 transition-transform cursor-pointer text-left">
          <p className="font-heading text-xl uppercase">AI Tools</p>
          <p className="text-sm text-zinc-500 mt-1">Promo generator, matchups & smart reminders</p>
        </button>
      </div>

      {/* Recent Events */}
      <div className="card-brutal">
        <div className="table-header-brutal p-4 flex items-center justify-between">
          <span className="text-lg">Recent Events</span>
          <button data-testid="view-all-events" onClick={() => navigate('/events')} className="text-sm font-mono text-zinc-400 hover:text-white flex items-center gap-1">
            View All <ArrowRight size={14} />
          </button>
        </div>
        <div className="divide-y-2 divide-zinc-100">
          {stats.recent_events?.length > 0 ? stats.recent_events.map((ev, i) => (
            <div key={i} className="p-4 flex items-center justify-between hover:bg-zinc-50 transition-colors">
              <div className="flex items-center gap-4">
                <div className="text-center w-16">
                  <p className="font-heading text-2xl leading-none">{ev.date ? new Date(ev.date).getDate() : '--'}</p>
                  <p className="font-mono text-xs uppercase text-zinc-500">{ev.date ? new Date(ev.date).toLocaleString('en', { month: 'short' }) : ''}</p>
                </div>
                <div>
                  <p className="font-semibold">{ev.title}</p>
                  <p className="text-sm text-zinc-500">{ev.venue}{ev.city ? `, ${ev.city}` : ''}</p>
                </div>
              </div>
              <span className={`badge-status ${ev.status === 'confirmed' ? 'border-green-600 text-green-700' : ev.status === 'announced' ? 'border-blue-600 text-blue-700' : 'border-zinc-400 text-zinc-600'}`}>
                {ev.status}
              </span>
            </div>
          )) : (
            <div className="p-8 text-center text-zinc-400">No events yet. Create your first event!</div>
          )}
        </div>
      </div>
    </div>
  );
}
