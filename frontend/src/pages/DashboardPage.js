import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import {
  CalendarBlank, UsersFour, Trophy, ListChecks,
  CurrencyDollar, TrendUp, ArrowRight
} from '@phosphor-icons/react';
import { useNavigate } from 'react-router-dom';

export default function DashboardPage() {
  const { api, user } = useAuth();
  const [stats, setStats] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    api.get('/dashboard/stats').then(r => setStats(r.data)).catch(console.error);
  }, [api]);

  if (!stats) return <PageLoader />;

  const statCards = [
    { label: 'Total Events', value: stats.total_events, icon: CalendarBlank, color: '#DC2626' },
    { label: 'Active Fighters', value: stats.total_fighters, icon: UsersFour, color: '#09090B' },
    { label: 'Upcoming Events', value: stats.upcoming_events, icon: Trophy, color: '#D4AF37' },
    { label: 'Pending Tasks', value: stats.tasks_pending, icon: ListChecks, color: '#DC2626' },
    { label: 'Total Revenue', value: `$${(stats.total_revenue || 0).toLocaleString()}`, icon: CurrencyDollar, color: '#16A34A' },
    { label: 'Net Profit', value: `$${(stats.net_profit || 0).toLocaleString()}`, icon: TrendUp, color: stats.net_profit >= 0 ? '#16A34A' : '#DC2626' },
  ];

  return (
    <div data-testid="dashboard-page" className="animate-in">
      <div className="mb-8">
        <h1 className="font-heading text-5xl uppercase leading-none">Command Center</h1>
        <p className="text-zinc-500 mt-1">Welcome back, {user?.name || 'Promoter'}</p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5 mb-8">
        {statCards.map((card, i) => (
          <div key={i} data-testid={`stat-${card.label.toLowerCase().replace(/\s/g, '-')}`} className="card-brutal p-5" style={{ animationDelay: `${i * 50}ms` }}>
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

function PageLoader() {
  return (
    <div className="flex items-center justify-center h-64">
      <div className="w-8 h-8 bg-[#DC2626] animate-pulse" />
    </div>
  );
}
