import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { CurrencyDollar } from '@phosphor-icons/react';

export default function FighterPayments() {
  const { api } = useAuth();
  const [data, setData] = useState({ payments: [], total_earnings: 0 });
  useEffect(() => { api.get('/fighter-portal/payments').then(r => setData(r.data)).catch(console.error); }, [api]);
  return (
    <div data-testid="fighter-payments-page" className="animate-in">
      <h1 className="font-heading text-4xl text-white uppercase mb-6">Payments</h1>
      <div className="bg-zinc-900 border border-zinc-800 p-6 mb-6 flex items-center gap-4">
        <div className="w-12 h-12 bg-green-600 flex items-center justify-center"><CurrencyDollar size={24} weight="bold" className="text-white" /></div>
        <div><p className="font-mono text-xs text-zinc-500 uppercase">Total Career Earnings</p><p className="font-heading text-4xl text-green-400">${(data.total_earnings || 0).toLocaleString()}</p></div>
      </div>
      {data.payments.length === 0 ? <div className="bg-zinc-900 border border-zinc-800 p-12 text-center text-zinc-600">No payment records</div> : (
        <div className="bg-zinc-900 border border-zinc-800 overflow-hidden">
          <table className="w-full">
            <thead><tr className="bg-zinc-800"><th className="text-left p-4 font-heading text-sm text-zinc-300 uppercase">Event</th><th className="text-left p-4 font-heading text-sm text-zinc-300 uppercase">Type</th><th className="text-right p-4 font-heading text-sm text-zinc-300 uppercase">Purse</th><th className="text-right p-4 font-heading text-sm text-zinc-300 uppercase">Win Bonus</th><th className="text-right p-4 font-heading text-sm text-zinc-300 uppercase">Total</th><th className="text-center p-4 font-heading text-sm text-zinc-300 uppercase">Status</th></tr></thead>
            <tbody className="divide-y divide-zinc-800">
              {data.payments.map(p => (
                <tr key={p._id} className="hover:bg-zinc-800/50">
                  <td className="p-4 text-white">{p.event_title || 'N/A'}</td>
                  <td className="p-4 text-zinc-400 text-sm">{p.type?.replace(/_/g, ' ')}</td>
                  <td className="p-4 text-right font-heading text-[#D4AF37]">${(p.purse || 0).toLocaleString()}</td>
                  <td className="p-4 text-right font-heading text-green-400">${(p.win_bonus || 0).toLocaleString()}</td>
                  <td className="p-4 text-right font-heading text-lg text-white">${((p.purse || 0) + (p.win_bonus || 0)).toLocaleString()}</td>
                  <td className="p-4 text-center"><span className="font-mono text-xs text-green-400">{p.status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
