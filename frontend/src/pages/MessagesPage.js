import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { ChatCircle, PaperPlaneTilt, Circle } from '@phosphor-icons/react';

export default function MessagesPage() {
  const { api, user: currentUser } = useAuth();
  const [messages, setMessages] = useState([]);
  const [users, setUsers] = useState([]);
  const [form, setForm] = useState({ to_type: 'broadcast', to_id: '', to_name: '', subject: '', body: '', priority: 'normal' });
  const [showCompose, setShowCompose] = useState(false);

  const load = () => {
    api.get('/messages').then(r => setMessages(r.data)).catch(console.error);
    api.get('/users').then(r => setUsers(r.data)).catch(() => {});
  };
  useEffect(() => { load(); }, [api]);

  const sendMessage = async (e) => {
    e.preventDefault();
    const selectedUser = users.find(u => u._id === form.to_id);
    await api.post('/messages', { ...form, to_name: selectedUser?.name || 'All Team' });
    setShowCompose(false);
    setForm({ to_type: 'broadcast', to_id: '', to_name: '', subject: '', body: '', priority: 'normal' });
    load();
  };

  const markRead = async (id) => { await api.patch(`/messages/${id}/read`); load(); };
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  return (
    <div data-testid="messages-page" className="animate-in">
      <div className="flex items-center justify-between mb-8">
        <div><h1 className="font-heading text-5xl uppercase leading-none">Messages</h1><p className="text-zinc-500 mt-1">Internal team communication</p></div>
        <button data-testid="compose-btn" onClick={() => setShowCompose(true)} className="btn-accent flex items-center gap-2"><PaperPlaneTilt size={18} weight="bold" /> Compose</button>
      </div>

      {showCompose && (
        <div className="card-brutal mb-6 overflow-hidden">
          <div className="bg-zinc-950 text-white p-4"><h3 className="font-heading text-xl uppercase">New Message</h3></div>
          <form onSubmit={sendMessage} className="p-6 space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div><label className="font-mono text-xs uppercase text-zinc-500 mb-1 block">To</label>
                <select data-testid="msg-to" value={form.to_id} onChange={e => setForm({ ...form, to_id: e.target.value, to_type: e.target.value ? 'user' : 'broadcast' })} className="select-brutal">
                  <option value="">All Team (Broadcast)</option>
                  {users.map(u => <option key={u._id} value={u._id}>{u.name} ({u.role})</option>)}
                </select>
              </div>
              <div><label className="font-mono text-xs uppercase text-zinc-500 mb-1 block">Priority</label><select value={form.priority} onChange={set('priority')} className="select-brutal"><option value="normal">Normal</option><option value="urgent">Urgent</option><option value="low">Low</option></select></div>
            </div>
            <div><label className="font-mono text-xs uppercase text-zinc-500 mb-1 block">Subject</label><input data-testid="msg-subject" value={form.subject} onChange={set('subject')} className="input-brutal" placeholder="Re: Event logistics" required /></div>
            <div><label className="font-mono text-xs uppercase text-zinc-500 mb-1 block">Message</label><textarea data-testid="msg-body" value={form.body} onChange={set('body')} className="input-brutal h-24 resize-none" required /></div>
            <div className="flex gap-2"><button data-testid="send-msg-btn" type="submit" className="btn-accent">Send Message</button><button type="button" onClick={() => setShowCompose(false)} className="btn-primary">Cancel</button></div>
          </form>
        </div>
      )}

      {messages.length === 0 ? (
        <div className="card-brutal p-12 text-center"><ChatCircle size={48} className="mx-auto mb-4 text-zinc-200" /><p className="font-heading text-3xl uppercase text-zinc-300">No Messages</p><p className="text-zinc-500">Start a conversation with your team</p></div>
      ) : (
        <div className="space-y-2">
          {messages.map(m => (
            <div key={m._id} data-testid={`msg-${m._id}`} onClick={() => !m.read && m.to_id === currentUser?._id && markRead(m._id)} className={`card-brutal p-4 cursor-pointer flex items-start gap-3 ${!m.read && m.to_id === currentUser?._id ? 'border-l-4 border-l-[#DC2626]' : ''}`}>
              <div className={`w-8 h-8 flex items-center justify-center flex-shrink-0 font-heading text-xs ${m.priority === 'urgent' ? 'bg-[#DC2626] text-white' : 'bg-zinc-200'}`}>
                {m.from_name?.charAt(0)?.toUpperCase() || '?'}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-sm">{m.from_name || 'System'}</span>
                  <span className="font-mono text-xs text-zinc-400">{m.to_type === 'broadcast' ? 'to All Team' : `to ${m.to_name || ''}`}</span>
                  {!m.read && m.to_id === currentUser?._id && <Circle size={8} weight="fill" className="text-[#DC2626]" />}
                </div>
                <p className="font-semibold text-sm mt-0.5">{m.subject}</p>
                <p className="text-sm text-zinc-500 truncate">{m.body}</p>
                <p className="font-mono text-xs text-zinc-400 mt-1">{m.created_at ? new Date(m.created_at).toLocaleString() : ''}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
