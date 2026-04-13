import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { FirstAid, CheckCircle, Warning, Clock } from '@phosphor-icons/react';

export default function FighterMedicals() {
  const { api } = useAuth();
  const [data, setData] = useState({ clearances: [], suspensions: [] });
  useEffect(() => { api.get('/fighter-portal/medicals').then(r => setData(r.data)).catch(console.error); }, [api]);

  return (
    <div data-testid="fighter-medicals-page" className="animate-in">
      <h1 className="font-heading text-4xl text-white uppercase mb-6">Medical Status</h1>

      {/* Active Suspensions */}
      {data.suspensions.filter(s => !s.cleared).length > 0 && (
        <div className="bg-red-900/20 border border-red-800 p-4 mb-6">
          <h2 className="font-heading text-xl text-red-400 uppercase mb-3 flex items-center gap-2"><Warning size={20} weight="fill" /> Active Suspensions</h2>
          {data.suspensions.filter(s => !s.cleared).map(s => (
            <div key={s._id} className="bg-red-950/30 border border-red-900 p-3 mb-2 flex items-center justify-between">
              <div><p className="text-red-400 font-semibold">{s.type?.replace(/_/g, ' ')}</p><p className="text-red-300 text-sm">{s.reason}</p></div>
              <div className="text-right"><p className="font-mono text-sm text-red-400">{s.start_date} to {s.end_date}</p></div>
            </div>
          ))}
        </div>
      )}

      {/* Clearances */}
      <h2 className="font-heading text-xl text-white uppercase mb-3">Medical Clearances</h2>
      {data.clearances.length === 0 ? <div className="bg-zinc-900 border border-zinc-800 p-8 text-center text-zinc-600">No medical records</div> : (
        <div className="space-y-2">
          {data.clearances.map(c => (
            <div key={c._id} className="bg-zinc-900 border border-zinc-800 p-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                {c.result === 'cleared' ? <CheckCircle size={20} weight="fill" className="text-green-500" /> : c.result === 'pending' ? <Clock size={20} weight="fill" className="text-yellow-500" /> : <Warning size={20} weight="fill" className="text-red-500" />}
                <div><p className="text-white font-semibold">{c.type?.replace(/_/g, ' ')}</p>{c.doctor && <p className="text-zinc-500 text-sm">Dr. {c.doctor}</p>}</div>
              </div>
              <div className="text-right">
                <p className="font-mono text-sm text-zinc-400">{c.date}</p>
                {c.expiry && <p className="font-mono text-xs text-zinc-600">Expires: {c.expiry}</p>}
                <span className={`font-mono text-xs ${c.result === 'cleared' ? 'text-green-500' : c.result === 'pending' ? 'text-yellow-500' : 'text-red-500'}`}>{c.result}</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Cleared Suspensions */}
      {data.suspensions.filter(s => s.cleared).length > 0 && (
        <>
          <h2 className="font-heading text-xl text-zinc-500 uppercase mt-6 mb-3">Past Suspensions (Cleared)</h2>
          <div className="space-y-2">
            {data.suspensions.filter(s => s.cleared).map(s => (
              <div key={s._id} className="bg-zinc-900 border border-zinc-800 p-3 flex items-center justify-between opacity-60">
                <div><p className="text-zinc-400">{s.type?.replace(/_/g, ' ')}</p></div>
                <div className="flex items-center gap-2 text-green-600 text-xs font-mono"><CheckCircle size={14} weight="fill" /> Cleared {s.cleared_date?.slice(0, 10)}</div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
