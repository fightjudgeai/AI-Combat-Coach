import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Sparkle, Lightning, SpinnerGap, Bell } from '@phosphor-icons/react';

export default function AIToolsPage() {
  const { api } = useAuth();
  const [events, setEvents] = useState([]);
  const [promoForm, setPromoForm] = useState({ event_title: '', event_date: '', venue: '', main_event: '', style: 'hype' });
  const [promoResult, setPromoResult] = useState('');
  const [promoLoading, setPromoLoading] = useState(false);
  const [matchupWC, setMatchupWC] = useState('Welterweight');
  const [matchupResult, setMatchupResult] = useState('');
  const [matchupLoading, setMatchupLoading] = useState(false);
  const [reminderEventId, setReminderEventId] = useState('');
  const [reminderResult, setReminderResult] = useState('');
  const [reminderLoading, setReminderLoading] = useState(false);

  const WEIGHT_CLASSES = ['Strawweight', 'Flyweight', 'Bantamweight', 'Featherweight', 'Lightweight', 'Welterweight', 'Middleweight', 'Light Heavyweight', 'Heavyweight'];

  useEffect(() => { api.get('/events').then(r => setEvents(r.data)); }, [api]);

  const selectEvent = (id) => {
    const ev = events.find(e => e._id === id);
    if (ev) setPromoForm({ ...promoForm, event_title: ev.title, event_date: ev.date, venue: `${ev.venue}${ev.city ? ', ' + ev.city : ''}` });
  };

  const generatePromo = async () => {
    setPromoLoading(true); setPromoResult('');
    try {
      const { data } = await api.post('/ai/generate-promo', promoForm);
      setPromoResult(data.promo_text);
    } catch { setPromoResult('Failed to generate. Please try again.'); }
    setPromoLoading(false);
  };

  const generateMatchups = async () => {
    setMatchupLoading(true); setMatchupResult('');
    try {
      const { data } = await api.post('/ai/matchup-suggestions', { weight_class: matchupWC });
      setMatchupResult(data.message || (typeof data.suggestions === 'string' ? data.suggestions : JSON.stringify(data.suggestions, null, 2)));
    } catch { setMatchupResult('Failed to generate. Please try again.'); }
    setMatchupLoading(false);
  };

  const generateReminders = async () => {
    if (!reminderEventId) return;
    setReminderLoading(true); setReminderResult('');
    try {
      const { data } = await api.post('/ai/smart-reminders', { event_id: reminderEventId });
      setReminderResult(data.reminders);
    } catch { setReminderResult('Failed to generate. Please try again.'); }
    setReminderLoading(false);
  };

  const set = (k) => (e) => setPromoForm({ ...promoForm, [k]: e.target.value });

  return (
    <div data-testid="ai-tools-page" className="animate-in">
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-10 h-10 bg-[#D4AF37] flex items-center justify-center">
            <Sparkle weight="fill" className="text-zinc-950" size={24} />
          </div>
          <h1 className="font-heading text-5xl uppercase leading-none">AI Tools</h1>
        </div>
        <p className="text-zinc-500">AI-powered tools to supercharge your promotions</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Promo Generator */}
        <div className="card-brutal overflow-hidden">
          <div className="bg-zinc-950 p-4 border-l-4 border-l-[#D4AF37]">
            <h2 className="font-heading text-2xl uppercase text-white flex items-center gap-2">
              <Lightning weight="fill" className="text-[#D4AF37]" size={20} /> Promo Generator
            </h2>
            <p className="text-zinc-400 text-sm">Auto-generate hype promotional descriptions</p>
          </div>
          <div className="p-6 space-y-4">
            <div>
              <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Quick Fill from Event</label>
              <select data-testid="ai-promo-event-select" onChange={e => selectEvent(e.target.value)} className="select-brutal">
                <option value="">Select event to auto-fill</option>
                {events.map(ev => <option key={ev._id} value={ev._id}>{ev.title}</option>)}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Event Title</label>
                <input data-testid="ai-promo-title" value={promoForm.event_title} onChange={set('event_title')} className="input-brutal" />
              </div>
              <div>
                <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Date</label>
                <input data-testid="ai-promo-date" value={promoForm.event_date} onChange={set('event_date')} className="input-brutal" />
              </div>
            </div>
            <div>
              <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Venue</label>
              <input data-testid="ai-promo-venue" value={promoForm.venue} onChange={set('venue')} className="input-brutal" />
            </div>
            <div>
              <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Main Event (optional)</label>
              <input data-testid="ai-promo-main" value={promoForm.main_event} onChange={set('main_event')} className="input-brutal" />
            </div>
            <div>
              <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Style</label>
              <select data-testid="ai-promo-style" value={promoForm.style} onChange={set('style')} className="select-brutal">
                <option value="hype">Hype / Exciting</option>
                <option value="professional">Professional</option>
                <option value="dramatic">Dramatic / Cinematic</option>
                <option value="social_media">Social Media Post</option>
              </select>
            </div>
            <button data-testid="generate-promo-btn" onClick={generatePromo} disabled={promoLoading || !promoForm.event_title} className="btn-gold w-full text-center flex items-center justify-center gap-2 disabled:opacity-50">
              {promoLoading ? <><SpinnerGap size={20} className="animate-spin" /> Generating...</> : <><Sparkle weight="fill" size={20} /> Generate Promo</>}
            </button>
            {promoResult && (
              <div data-testid="promo-result" className="ai-highlight mt-4">
                <p className="font-mono text-xs uppercase tracking-widest text-[#D4AF37] mb-2">Generated Promo</p>
                <p className="whitespace-pre-wrap leading-relaxed">{promoResult}</p>
              </div>
            )}
          </div>
        </div>

        {/* Matchup Suggestions */}
        <div className="card-brutal overflow-hidden">
          <div className="bg-zinc-950 p-4 border-l-4 border-l-[#D4AF37]">
            <h2 className="font-heading text-2xl uppercase text-white flex items-center gap-2">
              <Sparkle weight="fill" className="text-[#D4AF37]" size={20} /> Matchup Suggestions
            </h2>
            <p className="text-zinc-400 text-sm">AI-powered fight matchup recommendations</p>
          </div>
          <div className="p-6 space-y-4">
            <div>
              <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Weight Class</label>
              <select data-testid="ai-matchup-weight" value={matchupWC} onChange={e => setMatchupWC(e.target.value)} className="select-brutal">
                {WEIGHT_CLASSES.map(wc => <option key={wc} value={wc}>{wc}</option>)}
              </select>
            </div>
            <button data-testid="generate-matchup-btn" onClick={generateMatchups} disabled={matchupLoading} className="btn-gold w-full text-center flex items-center justify-center gap-2 disabled:opacity-50">
              {matchupLoading ? <><SpinnerGap size={20} className="animate-spin" /> Analyzing...</> : <><Sparkle weight="fill" size={20} /> Suggest Matchups</>}
            </button>
            {matchupResult && (
              <div data-testid="matchup-result" className="ai-highlight mt-4">
                <p className="font-mono text-xs uppercase tracking-widest text-[#D4AF37] mb-2">AI Suggestions</p>
                <pre className="whitespace-pre-wrap text-sm leading-relaxed font-body">{matchupResult}</pre>
              </div>
            )}
          </div>
        </div>

        {/* Smart Reminders */}
        <div className="card-brutal overflow-hidden lg:col-span-2">
          <div className="bg-zinc-950 p-4 border-l-4 border-l-[#DC2626]">
            <h2 className="font-heading text-2xl uppercase text-white flex items-center gap-2">
              <Bell weight="fill" className="text-[#DC2626]" size={20} /> Smart Reminders & Alerts
            </h2>
            <p className="text-zinc-400 text-sm">AI scans your event data to flag risks, missing tasks, and compliance issues</p>
          </div>
          <div className="p-6">
            <div className="flex gap-4 items-end mb-4">
              <div className="flex-1">
                <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Select Event</label>
                <select data-testid="ai-reminder-event" value={reminderEventId} onChange={e => setReminderEventId(e.target.value)} className="select-brutal">
                  <option value="">-- Choose event --</option>
                  {events.map(ev => <option key={ev._id} value={ev._id}>{ev.title}</option>)}
                </select>
              </div>
              <button data-testid="generate-reminders-btn" onClick={generateReminders} disabled={reminderLoading || !reminderEventId} className="btn-accent flex items-center gap-2 disabled:opacity-50">
                {reminderLoading ? <><SpinnerGap size={20} className="animate-spin" /> Scanning...</> : <><Bell weight="fill" size={20} /> Scan Event</>}
              </button>
            </div>
            {reminderResult && (
              <div data-testid="reminder-result" className="bg-red-50 border-2 border-[#DC2626] p-6">
                <p className="font-mono text-xs uppercase tracking-widest text-[#DC2626] mb-3">AI Risk Analysis & Reminders</p>
                <pre className="whitespace-pre-wrap text-sm leading-relaxed font-body">{reminderResult}</pre>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
