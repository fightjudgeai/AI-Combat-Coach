import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { ChatCircle, PaperPlaneTilt, Circle } from '@phosphor-icons/react';

export default function FighterMessages() {
  const { api, user: currentUser } = useAuth();
  const [messages, setMessages] = useState([]);
  const [showCompose, setShowCompose] = useState(false);
  const [form, setForm] = useState({ subject: '', body: '', priority: 'normal' });

  const load = () => api.get('/fighter-portal/messages').then(r => setMessages(r.data)).catch(console.error);
  useEffect(() => { load(); }, [api]);

  const send = async (e) => {
    e.preventDefault();
    await api.post('/fighter-portal/messages', { ...form, to_type: 'broadcast', to_id: '', to_name: 'Promoter' });
    setShowCompose(false); setForm({ subject: '', body: '', priority: 'normal' }); load();
  };

  return (
    <div data-testid="fighter-messages-page" className="animate-in">
      <div className="flex items-center justify-between mb-6">
        <h1 className="font-heading text-4xl text-white uppercase">Messages</h1>
        <button data-testid="fp-compose-btn" onClick={() => setShowCompose(!showCompose)} className="bg-[#DC2626] text-white font-heading uppercase px-4 py-2 text-sm flex items-center gap-2 hover:bg-red-700"><PaperPlaneTilt size={16} weight="bold" /> New Message</button>
      </div>

      {showCompose && (
        <form onSubmit={send} className="bg-zinc-900 border border-zinc-800 p-5 mb-6 space-y-3">
          <input data-testid="fp-msg-subject" value={form.subject} onChange={e => setForm({...form, subject: e.target.value})} className="w-full bg-zinc-800 border border-zinc-700 text-white p-2 text-sm outline-none focus:border-[#DC2626]" placeholder="Subject" required />
          <textarea data-testid="fp-msg-body" value={form.body} onChange={e => setForm({...form, body: e.target.value})} className="w-full bg-zinc-800 border border-zinc-700 text-white p-2 text-sm outline-none focus:border-[#DC2626] h-20 resize-none" placeholder="Your message..." required />
          <button data-testid="fp-send-msg" type="submit" className="bg-[#DC2626] text-white font-heading uppercase px-4 py-2 text-sm">Send to Promoter</button>
        </form>
      )}

      {messages.length === 0 ? (
        <div className="bg-zinc-900 border border-zinc-800 p-12 text-center"><ChatCircle size={48} className="mx-auto mb-4 text-zinc-700" /><p className="text-zinc-600">No messages yet</p></div>
      ) : (
        <div className="space-y-2">
          {messages.map(m => (
            <div key={m._id} className={`bg-zinc-900 border border-zinc-800 p-4 ${!m.read && m.to_id === currentUser?._id ? 'border-l-2 border-l-[#DC2626]' : ''}`}>
              <div className="flex items-center gap-2 mb-1">
                <div className="w-6 h-6 bg-zinc-800 flex items-center justify-center font-heading text-[10px] text-zinc-400">{m.from_name?.charAt(0) || '?'}</div>
                <span className="text-sm text-white font-semibold">{m.from_name}</span>
                <span className="text-xs text-zinc-600">{m.created_at ? new Date(m.created_at).toLocaleString() : ''}</span>
                {!m.read && m.to_id === currentUser?._id && <Circle size={8} weight="fill" className="text-[#DC2626]" />}
              </div>
              <p className="text-white text-sm font-semibold">{m.subject}</p>
              <p className="text-zinc-400 text-sm mt-1">{m.body}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
