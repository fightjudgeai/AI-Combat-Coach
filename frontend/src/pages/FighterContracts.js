import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';

export default function FighterContracts() {
  const { api } = useAuth();
  const [contracts, setContracts] = useState([]);
  useEffect(() => { api.get('/fighter-portal/contracts').then(r => setContracts(r.data)).catch(console.error); }, [api]);
  const statusColors = { pending: 'bg-yellow-500/20 text-yellow-400 border-yellow-800', signed: 'bg-blue-500/20 text-blue-400 border-blue-800', active: 'bg-green-500/20 text-green-400 border-green-800', completed: 'bg-zinc-500/20 text-zinc-400 border-zinc-700', terminated: 'bg-red-500/20 text-red-400 border-red-800' };
  return (
    <div data-testid="fighter-contracts-page" className="animate-in">
      <h1 className="font-heading text-4xl text-white uppercase mb-6">My Contracts</h1>
      {contracts.length === 0 ? <div className="bg-zinc-900 border border-zinc-800 p-12 text-center text-zinc-600">No contracts on file</div> : (
        <div className="space-y-4">
          {contracts.map(c => (
            <div key={c._id} className="bg-zinc-900 border border-zinc-800 overflow-hidden">
              <div className="p-4 flex items-center justify-between">
                <div>
                  <p className="text-white font-semibold">{c.type?.replace(/_/g, ' ').toUpperCase()}</p>
                  {c.event_title && <p className="text-zinc-400 text-sm">{c.event_title}</p>}
                </div>
                <span className={`text-xs font-mono px-2 py-1 border ${statusColors[c.status] || ''}`}>{c.status}</span>
              </div>
              <div className="grid grid-cols-4 gap-4 p-4 bg-zinc-950 border-t border-zinc-800">
                <div><p className="font-mono text-xs text-zinc-600 uppercase">Purse</p><p className="font-heading text-xl text-[#D4AF37]">${(c.purse || 0).toLocaleString()}</p></div>
                <div><p className="font-mono text-xs text-zinc-600 uppercase">Win Bonus</p><p className="font-heading text-xl text-green-400">${(c.win_bonus || 0).toLocaleString()}</p></div>
                <div><p className="font-mono text-xs text-zinc-600 uppercase">Start</p><p className="text-sm text-zinc-400">{c.start_date || 'TBD'}</p></div>
                <div><p className="font-mono text-xs text-zinc-600 uppercase">End</p><p className="text-sm text-zinc-400">{c.end_date || 'TBD'}</p></div>
              </div>
              {c.terms && <div className="p-4 border-t border-zinc-800 text-sm text-zinc-500">{c.terms}</div>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
