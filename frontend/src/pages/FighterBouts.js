import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Sword } from '@phosphor-icons/react';

export default function FighterBouts() {
  const { api } = useAuth();
  const [bouts, setBouts] = useState([]);
  useEffect(() => { api.get('/fighter-portal/bouts').then(r => setBouts(r.data)).catch(console.error); }, [api]);

  const upcoming = bouts.filter(b => b.status === 'scheduled' || b.status === 'in_progress');
  const past = bouts.filter(b => b.status === 'completed' || b.status === 'cancelled');

  return (
    <div data-testid="fighter-bouts-page" className="animate-in">
      <h1 className="font-heading text-4xl text-white uppercase mb-6">My Bouts</h1>

      <h2 className="font-heading text-xl text-[#DC2626] uppercase mb-3">Upcoming</h2>
      {upcoming.length === 0 ? <div className="bg-zinc-900 border border-zinc-800 p-8 text-center text-zinc-600 mb-6">No upcoming bouts</div> : (
        <div className="space-y-3 mb-6">
          {upcoming.map(b => (
            <div key={b._id} className="bg-zinc-900 border border-zinc-800 p-4 flex items-center gap-4">
              <Sword size={20} weight="bold" className="text-[#DC2626]" />
              <div className="flex-1">
                <p className="text-white font-semibold">{b.event_title || 'Event'} — {b.event_date}</p>
                <p className="text-zinc-400 text-sm">{b.fighter1_name} <span className="text-[#DC2626] font-heading mx-1">VS</span> {b.fighter2_name}</p>
              </div>
              <span className="badge-weight bg-zinc-800 text-zinc-300">{b.weight_class}</span>
              <span className="font-mono text-xs text-zinc-500">{b.rounds} RDS</span>
              <span className={`font-mono text-xs px-2 py-1 ${b.is_main_event ? 'bg-[#D4AF37] text-zinc-950' : 'bg-zinc-800 text-zinc-400'}`}>{b.is_main_event ? 'MAIN EVENT' : `#${b.bout_order}`}</span>
            </div>
          ))}
        </div>
      )}

      <h2 className="font-heading text-xl text-zinc-400 uppercase mb-3">Past Bouts</h2>
      {past.length === 0 ? <div className="bg-zinc-900 border border-zinc-800 p-8 text-center text-zinc-600">No past bouts</div> : (
        <div className="space-y-3">
          {past.map(b => (
            <div key={b._id} className="bg-zinc-900 border border-zinc-800 p-4 flex items-center gap-4 opacity-60">
              <div className="flex-1"><p className="text-white">{b.event_title} — {b.event_date}</p><p className="text-zinc-500 text-sm">{b.fighter1_name} vs {b.fighter2_name}</p></div>
              <span className="badge-weight bg-zinc-800 text-zinc-400">{b.weight_class}</span>
              <span className={`font-mono text-xs ${b.status === 'completed' ? 'text-green-500' : 'text-red-500'}`}>{b.status}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
