import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { ChatCircle, PaperPlaneTilt, Circle } from '@phosphor-icons/react';

export default function CoachMessages() {
  const { api, user: currentUser } = useAuth();
  const [messages, setMessages] = useState([]);
  const [showCompose, setShowCompose] = useState(false);
  const [form, setForm] = useState({ subject: '', body: '', priority: 'normal' });

  const load = () => api.get('/coach-portal/messages').then(r => setMessages(r.data)).catch(console.error);
  useEffect(() => { load(); }, [api]);

  const send = async (e) => {
    e.preventDefault();
    await api.post('/coach-portal/messages', { ...form, to_type: 'broadcast', to_id: '', to_name: 'Promoter' });
    setShowCompose(false); setForm({ subject: '', body: '', priority: 'normal' }); load();
  };

  return (
    <div data-testid="coach-messages-page" className="animate-in">
      <div className="flex items-center justify-between mb-6">
        <h1 className="font-heading text-4xl text-white uppercase">Messages</h1>
        <button data-testid="cp-compose-btn" onClick={() => setShowCompose(!showCompose)} className="bg-[#D4AF37] text-[#0d1f3c] font-heading uppercase px-4 py-2 text-sm flex items-center gap-2"><PaperPlaneTilt size={16} weight="bold" /> New Message</button>
      </div>
      {showCompose && (
        <form onSubmit={send} className="bg-[#0d1f3c] border border-[#1a3a6b] p-5 mb-6 space-y-3">
          <input value={form.subject} onChange={e => setForm({...form, subject: e.target.value})} className="w-full bg-[#091424] border border-[#1a3a6b] text-white p-2 text-sm outline-none focus:border-[#D4AF37]" placeholder="Subject" required />
          <textarea value={form.body} onChange={e => setForm({...form, body: e.target.value})} className="w-full bg-[#091424] border border-[#1a3a6b] text-white p-2 text-sm outline-none focus:border-[#D4AF37] h-20 resize-none" placeholder="Message..." required />
          <button type="submit" className="bg-[#D4AF37] text-[#0d1f3c] font-heading uppercase px-4 py-2 text-sm">Send</button>
        </form>
      )}
      {messages.length === 0 ? (
        <div className="bg-[#0d1f3c] border border-[#1a3a6b] p-12 text-center"><ChatCircle size={48} className="mx-auto mb-4 text-[#1a3a6b]" /><p className="text-blue-300/30">No messages</p></div>
      ) : (
        <div className="space-y-2">
          {messages.map(m => (
            <div key={m._id} className={`bg-[#0d1f3c] border border-[#1a3a6b] p-4 ${!m.read && m.to_id === currentUser?._id ? 'border-l-2 border-l-[#D4AF37]' : ''}`}>
              <div className="flex items-center gap-2 mb-1">
                <span className="text-sm text-white font-semibold">{m.from_name}</span>
                <span className="text-xs text-blue-300/30">{m.created_at ? new Date(m.created_at).toLocaleString() : ''}</span>
                {!m.read && m.to_id === currentUser?._id && <Circle size={8} weight="fill" className="text-[#D4AF37]" />}
              </div>
              <p className="text-white text-sm font-semibold">{m.subject}</p>
              <p className="text-blue-300/50 text-sm mt-1">{m.body}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
