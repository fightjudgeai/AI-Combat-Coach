import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';

export default function CoachFighters() {
  const { api } = useAuth();
  const [fighters, setFighters] = useState([]);
  useEffect(() => { api.get('/coach-portal/fighters').then(r => setFighters(r.data)).catch(console.error); }, [api]);

  return (
    <div data-testid="coach-fighters-page" className="animate-in">
      <h1 className="font-heading text-4xl text-white uppercase mb-6">My Fighters</h1>
      {fighters.length === 0 ? <div className="bg-[#0d1f3c] border border-[#1a3a6b] p-12 text-center text-blue-300/30">No fighters linked to your gym</div> : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {fighters.map(f => (
            <div key={f._id} className="bg-[#0d1f3c] border border-[#1a3a6b] overflow-hidden">
              <div className="p-4 flex items-center gap-4">
                <div className="w-14 h-14 bg-[#1a3a6b] flex items-center justify-center font-heading text-2xl text-[#D4AF37]">{f.name?.charAt(0)}</div>
                <div className="flex-1">
                  <p className="text-white font-semibold text-lg">{f.name}</p>
                  {f.nickname && <p className="text-[#D4AF37] text-sm">"{f.nickname}"</p>}
                </div>
                <span className={`text-xs font-mono px-2 py-1 ${f.status === 'active' ? 'bg-green-900/30 text-green-400 border border-green-800' : 'bg-red-900/30 text-red-400 border border-red-800'}`}>{f.status}</span>
              </div>
              <div className="grid grid-cols-4 gap-3 p-4 bg-[#091424] border-t border-[#1a3a6b] text-center">
                <div><p className="font-mono text-[10px] text-blue-300/40 uppercase">Weight</p><p className="text-white text-sm font-semibold">{f.weight_class}</p></div>
                <div><p className="font-mono text-[10px] text-blue-300/40 uppercase">Record</p><p className="font-heading text-xl text-white">{f.wins}-{f.losses}-{f.draws}</p></div>
                <div><p className="font-mono text-[10px] text-blue-300/40 uppercase">Age</p><p className="text-white text-sm">{f.age || '-'}</p></div>
                <div><p className="font-mono text-[10px] text-blue-300/40 uppercase">Stance</p><p className="text-white text-sm capitalize">{f.stance || '-'}</p></div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
