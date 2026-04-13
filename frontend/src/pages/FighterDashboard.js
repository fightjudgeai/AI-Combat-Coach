import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Sword, FirstAid, FileText, CurrencyDollar, ChatCircle, Warning } from '@phosphor-icons/react';
import { useNavigate } from 'react-router-dom';

export default function FighterDashboard() {
  const { api, user } = useAuth();
  const [data, setData] = useState(null);
  const navigate = useNavigate();

  useEffect(() => { api.get('/fighter-portal/dashboard').then(r => setData(r.data)).catch(console.error); }, [api]);

  if (!data) return <div className="flex items-center justify-center h-64"><div className="w-8 h-8 bg-[#DC2626] animate-pulse" /></div>;

  const fighter = data.fighter || {};

  return (
    <div data-testid="fighter-dashboard" className="animate-in">
      {/* Fighter Header */}
      <div className="bg-zinc-900 border border-zinc-800 p-6 mb-6">
        <div className="flex items-center gap-6">
          <div className="w-20 h-20 bg-[#DC2626] flex items-center justify-center font-heading text-4xl text-white">
            {fighter.name?.charAt(0) || 'F'}
          </div>
          <div>
            <h1 className="font-heading text-4xl text-white uppercase leading-none">{fighter.name}</h1>
            {fighter.nickname && <p className="text-[#D4AF37] font-heading text-xl uppercase mt-1">"{fighter.nickname}"</p>}
            <div className="flex items-center gap-4 mt-2">
              <span className="badge-weight bg-zinc-800 text-white">{fighter.weight_class}</span>
              <span className="font-heading text-2xl text-white">{data.record}</span>
              {fighter.gym && <span className="text-zinc-500 text-sm">{fighter.gym}</span>}
            </div>
          </div>
        </div>
      </div>

      {/* Alerts */}
      {(data.active_suspensions > 0 || data.pending_clearances > 0) && (
        <div className="bg-red-900/30 border border-red-800 p-4 mb-6 flex items-center gap-3">
          <Warning size={24} weight="fill" className="text-red-500" />
          <div>
            {data.active_suspensions > 0 && <p className="text-red-400 font-semibold">{data.active_suspensions} active medical suspension(s)</p>}
            {data.pending_clearances > 0 && <p className="text-yellow-400 font-semibold">{data.pending_clearances} pending medical clearance(s)</p>}
          </div>
        </div>
      )}

      {/* Quick Stats */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
        {[
          { label: 'Upcoming Bouts', value: data.upcoming_bouts?.length || 0, icon: Sword, color: '#DC2626' },
          { label: 'Suspensions', value: data.active_suspensions, icon: FirstAid, color: data.active_suspensions > 0 ? '#DC2626' : '#16A34A' },
          { label: 'Pending Contracts', value: data.contracts_pending, icon: FileText, color: '#D4AF37' },
          { label: 'Total Earnings', value: `$${(data.total_earnings || 0).toLocaleString()}`, icon: CurrencyDollar, color: '#16A34A' },
          { label: 'Unread Messages', value: data.unread_messages, icon: ChatCircle, color: '#3B82F6' },
        ].map((stat, i) => (
          <div key={i} className="bg-zinc-900 border border-zinc-800 p-4">
            <div className="flex items-center gap-2 mb-2">
              <stat.icon size={16} weight="bold" style={{ color: stat.color }} />
              <span className="font-mono text-[10px] uppercase tracking-widest text-zinc-500">{stat.label}</span>
            </div>
            <p className="font-heading text-2xl text-white">{stat.value}</p>
          </div>
        ))}
      </div>

      {/* Upcoming Bouts */}
      <div className="bg-zinc-900 border border-zinc-800 mb-6">
        <div className="bg-zinc-800 p-4 flex items-center justify-between">
          <span className="font-heading text-lg uppercase text-white">Upcoming Bouts</span>
          <button onClick={() => navigate('/fighter-portal/bouts')} className="text-xs font-mono text-zinc-400 hover:text-white">View All</button>
        </div>
        {data.upcoming_bouts?.length > 0 ? data.upcoming_bouts.map((bout, i) => (
          <div key={i} className="p-4 border-t border-zinc-800 flex items-center gap-4">
            <div className="text-center w-14">
              <p className="font-heading text-xl text-white">{bout.event_date ? new Date(bout.event_date).getDate() : '--'}</p>
              <p className="font-mono text-xs text-zinc-500">{bout.event_date ? new Date(bout.event_date).toLocaleString('en', { month: 'short' }) : ''}</p>
            </div>
            <div className="flex-1">
              <p className="text-white font-semibold">{bout.event_title}</p>
              <p className="text-sm text-zinc-400">
                {bout.fighter1_name} <span className="text-[#DC2626] font-heading mx-2">VS</span> {bout.fighter2_name}
              </p>
            </div>
            <span className="badge-weight bg-zinc-800 text-zinc-300">{bout.weight_class}</span>
            <span className="font-mono text-xs text-zinc-500">{bout.rounds} RDS</span>
          </div>
        )) : (
          <div className="p-8 text-center text-zinc-600">No upcoming bouts scheduled</div>
        )}
      </div>

      {/* Quick Links */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: 'Medical Status', to: '/fighter-portal/medicals', color: '#DC2626' },
          { label: 'My Contracts', to: '/fighter-portal/contracts', color: '#D4AF37' },
          { label: 'Payments', to: '/fighter-portal/payments', color: '#16A34A' },
          { label: 'Edit Profile', to: '/fighter-portal/profile', color: '#3B82F6' },
        ].map((link, i) => (
          <button key={i} onClick={() => navigate(link.to)} className="bg-zinc-900 border border-zinc-800 p-4 text-left hover:border-zinc-600 transition-colors cursor-pointer">
            <p className="font-heading text-lg uppercase text-white">{link.label}</p>
            <div className="w-8 h-1 mt-2" style={{ background: link.color }} />
          </button>
        ))}
      </div>
    </div>
  );
}
