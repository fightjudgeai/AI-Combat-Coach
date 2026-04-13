import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Megaphone, Plus, Trash, X, Sparkle, SpinnerGap, PaperPlaneTilt } from '@phosphor-icons/react';

const CAMPAIGN_TYPES = ['email', 'sms', 'social_post'];
const AUDIENCES = ['all', 'ticket_buyers', 'fighters', 'sponsors', 'media', 'vip'];

export default function MarketingPage() {
  const { api } = useAuth();
  const [campaigns, setCampaigns] = useState([]);
  const [events, setEvents] = useState([]);
  const [showModal, setShowModal] = useState(false);
  const [generating, setGenerating] = useState('');
  const [form, setForm] = useState({ name: '', type: 'email', event_id: '', content: '', target_audience: 'all', scheduled_at: '', status: 'draft' });

  const load = () => {
    api.get('/campaigns').then(r => setCampaigns(r.data)).catch(console.error);
    api.get('/events').then(r => setEvents(r.data)).catch(console.error);
  };
  useEffect(() => { load(); }, [api]);

  const handleSubmit = async (e) => { e.preventDefault(); await api.post('/campaigns', form); setShowModal(false); load(); };

  const generateContent = async (id) => {
    setGenerating(id);
    try { const { data } = await api.post(`/campaigns/${id}/generate-content`); load(); } catch { alert('Generation failed'); }
    setGenerating('');
  };

  const deleteCampaign = async (id) => { if (window.confirm('Delete campaign?')) { await api.delete(`/campaigns/${id}`); load(); } };
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const typeIcons = { email: 'EMAIL', sms: 'SMS', social_post: 'SOCIAL' };
  const typeColors = { email: 'bg-blue-100 text-blue-700', sms: 'bg-green-100 text-green-700', social_post: 'bg-purple-100 text-purple-700' };

  return (
    <div data-testid="marketing-page" className="animate-in">
      <div className="flex items-center gap-4 mb-8">
        <div className="w-12 h-12 bg-[#DC2626] flex items-center justify-center"><Megaphone weight="fill" className="text-white" size={28} /></div>
        <div><h1 className="font-heading text-5xl uppercase leading-none">Marketing</h1><p className="text-zinc-500">Campaign management & content generation</p></div>
      </div>

      <div className="flex justify-end mb-6">
        <button data-testid="create-campaign-btn" onClick={() => { setForm({ name: '', type: 'email', event_id: '', content: '', target_audience: 'all', scheduled_at: '', status: 'draft' }); setShowModal(true); }} className="btn-accent flex items-center gap-2"><Plus size={18} weight="bold" /> New Campaign</button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div className="card-brutal p-4 text-center"><p className="font-mono text-xs uppercase text-zinc-500">Total</p><p className="stat-value">{campaigns.length}</p></div>
        <div className="card-brutal p-4 text-center"><p className="font-mono text-xs uppercase text-zinc-500">Drafts</p><p className="stat-value">{campaigns.filter(c => c.status === 'draft').length}</p></div>
        <div className="card-brutal p-4 text-center"><p className="font-mono text-xs uppercase text-zinc-500">Scheduled</p><p className="stat-value text-blue-600">{campaigns.filter(c => c.status === 'scheduled').length}</p></div>
        <div className="card-brutal p-4 text-center"><p className="font-mono text-xs uppercase text-zinc-500">Sent</p><p className="stat-value text-green-600">{campaigns.filter(c => c.status === 'sent').length}</p></div>
      </div>

      {campaigns.length === 0 ? (
        <div className="card-brutal p-12 text-center"><Megaphone size={48} className="mx-auto mb-4 text-zinc-200" /><p className="font-heading text-3xl uppercase text-zinc-300">No Campaigns</p><p className="text-zinc-500">Create your first marketing campaign</p></div>
      ) : (
        <div className="space-y-4">
          {campaigns.map(c => {
            const eventName = events.find(e => e._id === c.event_id)?.title;
            return (
              <div key={c._id} data-testid={`campaign-${c._id}`} className="card-brutal overflow-hidden">
                <div className="p-4 flex items-center gap-4">
                  <span className={`font-mono text-xs font-bold px-2 py-1 ${typeColors[c.type] || 'bg-zinc-100'}`}>{typeIcons[c.type] || c.type}</span>
                  <div className="flex-1 min-w-0">
                    <p className="font-semibold">{c.name}</p>
                    <div className="flex items-center gap-3 text-xs text-zinc-500 mt-0.5">
                      {eventName && <span>{eventName}</span>}
                      <span>Target: {c.target_audience}</span>
                      {c.scheduled_at && <span>Scheduled: {c.scheduled_at}</span>}
                    </div>
                  </div>
                  <span className={`badge-status text-xs ${c.status === 'sent' ? 'border-green-600 text-green-700' : c.status === 'scheduled' ? 'border-blue-600 text-blue-700' : 'border-zinc-400 text-zinc-500'}`}>{c.status}</span>
                  <button onClick={() => generateContent(c._id)} disabled={generating === c._id} className="btn-gold text-xs py-1.5 px-3 flex items-center gap-1 disabled:opacity-50">
                    {generating === c._id ? <SpinnerGap size={14} className="animate-spin" /> : <Sparkle size={14} weight="fill" />} AI Write
                  </button>
                  <button onClick={() => deleteCampaign(c._id)} className="p-2 hover:text-red-600"><Trash size={16} weight="bold" /></button>
                </div>
                {c.content && (
                  <div className="border-t-2 border-zinc-100 p-4 bg-zinc-50"><p className="text-sm whitespace-pre-wrap">{c.content}</p></div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {showModal && (
        <div className="fixed inset-0 modal-overlay flex items-center justify-center z-50 p-4" onClick={() => setShowModal(false)}>
          <div className="bg-white border-2 border-zinc-950 shadow-[8px_8px_0px_0px_rgba(9,9,11,1)] w-full max-w-lg animate-in" onClick={e => e.stopPropagation()}>
            <div className="bg-zinc-950 text-white p-4 flex items-center justify-between"><h2 className="font-heading text-2xl uppercase">New Campaign</h2><button onClick={() => setShowModal(false)}><X size={20} className="text-white" /></button></div>
            <form onSubmit={handleSubmit} className="p-6 space-y-4">
              <div><label className="font-mono text-xs uppercase text-zinc-500 mb-1 block">Campaign Name</label><input data-testid="campaign-name" value={form.name} onChange={set('name')} className="input-brutal" placeholder="Fight Night Promo Blast" required /></div>
              <div className="grid grid-cols-2 gap-4"><div><label className="font-mono text-xs uppercase text-zinc-500 mb-1 block">Type</label><select value={form.type} onChange={set('type')} className="select-brutal">{CAMPAIGN_TYPES.map(t => <option key={t} value={t}>{t.replace('_', ' ')}</option>)}</select></div><div><label className="font-mono text-xs uppercase text-zinc-500 mb-1 block">Audience</label><select value={form.target_audience} onChange={set('target_audience')} className="select-brutal">{AUDIENCES.map(a => <option key={a} value={a}>{a.replace('_', ' ')}</option>)}</select></div></div>
              <div><label className="font-mono text-xs uppercase text-zinc-500 mb-1 block">Event (optional)</label><select value={form.event_id} onChange={set('event_id')} className="select-brutal"><option value="">None</option>{events.map(e => <option key={e._id} value={e._id}>{e.title}</option>)}</select></div>
              <div><label className="font-mono text-xs uppercase text-zinc-500 mb-1 block">Content (or use AI to generate)</label><textarea value={form.content} onChange={set('content')} className="input-brutal h-24 resize-none" /></div>
              <button type="submit" className="btn-accent w-full text-center">Create Campaign</button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
