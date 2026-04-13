import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { UsersFour, Sword, Warning, ChatCircle } from '@phosphor-icons/react';
import { useNavigate } from 'react-router-dom';

export default function CoachDashboard() {
  const { api, user } = useAuth();
  const [data, setData] = useState(null);
  const navigate = useNavigate();

  useEffect(() => { api.get('/coach-portal/dashboard').then(r => setData(r.data)).catch(console.error); }, [api]);
  if (!data) return <div className="flex items-center justify-center h-64"><div className="w-8 h-8 bg-[#D4AF37] animate-pulse" /></div>;

  return (
    <div data-testid="coach-dashboard" className="animate-in">
      <div className="bg-[#0d1f3c] border border-[#1a3a6b] p-6 mb-6">
        <p className="font-mono text-xs text-[#D4AF37] uppercase tracking-widest mb-1">{data.gym}</p>
        <h1 className="font-heading text-4xl text-white uppercase">Coach {data.coach_name}</h1>
        <p className="text-blue-300/50 mt-1">{data.fighters_count} fighters in your gym</p>
      </div>

      {data.active_suspensions > 0 && (
        <div className="bg-red-900/20 border border-red-800 p-4 mb-6 flex items-center gap-3">
          <Warning size={24} weight="fill" className="text-red-500" />
          <p className="text-red-400 font-semibold">{data.active_suspensions} fighter(s) with active medical suspensions</p>
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        {[
          { label: 'My Fighters', value: data.fighters_count, icon: UsersFour, color: '#D4AF37' },
          { label: 'Upcoming Bouts', value: data.upcoming_bouts?.length || 0, icon: Sword, color: '#DC2626' },
          { label: 'Suspensions', value: data.active_suspensions, icon: Warning, color: data.active_suspensions > 0 ? '#DC2626' : '#16A34A' },
          { label: 'Unread Messages', value: data.unread_messages, icon: ChatCircle, color: '#3B82F6' },
        ].map((stat, i) => (
          <div key={i} className="bg-[#0d1f3c] border border-[#1a3a6b] p-4">
            <div className="flex items-center gap-2 mb-2">
              <stat.icon size={16} weight="bold" style={{ color: stat.color }} />
              <span className="font-mono text-[10px] uppercase tracking-widest text-blue-300/40">{stat.label}</span>
            </div>
            <p className="font-heading text-2xl text-white">{stat.value}</p>
          </div>
        ))}
      </div>

      {/* Fighters Roster */}
      <div className="bg-[#0d1f3c] border border-[#1a3a6b] mb-6">
        <div className="bg-[#1a3a6b] p-4 flex items-center justify-between">
          <span className="font-heading text-lg uppercase text-white">My Fighters</span>
          <button onClick={() => navigate('/coach-portal/fighters')} className="text-xs font-mono text-blue-300/50 hover:text-white">View All</button>
        </div>
        {data.fighters?.length > 0 ? data.fighters.map(f => (
          <div key={f._id} className="p-4 border-t border-[#1a3a6b] flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-[#1a3a6b] flex items-center justify-center font-heading text-sm text-[#D4AF37]">{f.name?.charAt(0)}</div>
              <div>
                <p className="text-white font-semibold">{f.name}</p>
                {f.nickname && <p className="text-[#D4AF37] text-xs">"{f.nickname}"</p>}
              </div>
            </div>
            <div className="flex items-center gap-4">
              <span className="font-mono text-xs bg-[#1a3a6b] text-blue-300 px-2 py-1">{f.weight_class}</span>
              <span className="font-heading text-lg text-white">{f.wins}-{f.losses}-{f.draws}</span>
              <span className={`text-xs font-mono ${f.status === 'active' ? 'text-green-400' : 'text-red-400'}`}>{f.status}</span>
            </div>
          </div>
        )) : <div className="p-8 text-center text-blue-300/30">No fighters in your gym yet</div>}
      </div>

      {/* Upcoming Bouts */}
      <div className="bg-[#0d1f3c] border border-[#1a3a6b]">
        <div className="bg-[#1a3a6b] p-4"><span className="font-heading text-lg uppercase text-white">Upcoming Bouts</span></div>
        {data.upcoming_bouts?.length > 0 ? data.upcoming_bouts.map((bout, i) => (
          <div key={i} className="p-4 border-t border-[#1a3a6b] flex items-center gap-4">
            <div className="w-14 text-center">
              <p className="font-heading text-xl text-white">{bout.event_date ? new Date(bout.event_date).getDate() : '--'}</p>
              <p className="font-mono text-xs text-blue-300/40">{bout.event_date ? new Date(bout.event_date).toLocaleString('en', { month: 'short' }) : ''}</p>
            </div>
            <div className="flex-1">
              <p className="text-white text-sm">{bout.event_title}</p>
              <p className="text-blue-300/60 text-sm">{bout.fighter1_name} <span className="text-[#DC2626] font-heading mx-1">VS</span> {bout.fighter2_name}</p>
            </div>
            <span className="font-mono text-xs bg-[#1a3a6b] text-blue-300 px-2 py-1">{bout.weight_class}</span>
          </div>
        )) : <div className="p-8 text-center text-blue-300/30">No upcoming bouts for your fighters</div>}
      </div>
    </div>
  );
}
