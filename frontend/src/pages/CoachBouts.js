import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Sword } from '@phosphor-icons/react';

export default function CoachBouts() {
  const { api } = useAuth();
  const [bouts, setBouts] = useState([]);
  useEffect(() => { api.get('/coach-portal/bouts').then(r => setBouts(r.data)).catch(console.error); }, [api]);

  return (
    <div data-testid="coach-bouts-page" className="animate-in">
      <h1 className="font-heading text-4xl text-white uppercase mb-6">Fighter Bouts</h1>
      {bouts.length === 0 ? <div className="bg-[#0d1f3c] border border-[#1a3a6b] p-12 text-center text-blue-300/30">No bouts scheduled for your fighters</div> : (
        <div className="space-y-3">
          {bouts.map(b => (
            <div key={b._id} className="bg-[#0d1f3c] border border-[#1a3a6b] p-4 flex items-center gap-4">
              <Sword size={20} weight="bold" className="text-[#D4AF37]" />
              <div className="flex-1">
                <p className="text-white font-semibold">{b.event_title || 'Event'} — {b.event_date}</p>
                <p className="text-blue-300/60 text-sm">{b.fighter1_name} <span className="text-[#DC2626] font-heading mx-1">VS</span> {b.fighter2_name}</p>
              </div>
              <span className="font-mono text-xs bg-[#1a3a6b] text-blue-300 px-2 py-1">{b.weight_class}</span>
              <span className="font-mono text-xs text-blue-300/40">{b.rounds} RDS</span>
              <span className={`font-mono text-xs ${b.status === 'scheduled' ? 'text-yellow-400' : b.status === 'completed' ? 'text-green-400' : 'text-blue-300/40'}`}>{b.status}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
