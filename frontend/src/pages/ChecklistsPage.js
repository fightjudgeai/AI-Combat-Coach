import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { ClipboardText, Play, Trash, CheckCircle } from '@phosphor-icons/react';

const TYPE_LABELS = { daily: 'Daily', weekly: 'Weekly', monthly: 'Monthly', event_day: 'Event Day' };
const TYPE_COLORS = { daily: 'bg-blue-100 text-blue-700 border-blue-300', weekly: 'bg-purple-100 text-purple-700 border-purple-300', monthly: 'bg-amber-100 text-amber-700 border-amber-300', event_day: 'bg-red-100 text-red-700 border-red-300' };

export default function ChecklistsPage() {
  const { api } = useAuth();
  const [templates, setTemplates] = useState([]);
  const [events, setEvents] = useState([]);
  const [applyEvent, setApplyEvent] = useState('');
  const [applyResult, setApplyResult] = useState(null);

  const load = () => {
    api.get('/checklists/templates').then(r => setTemplates(r.data));
    api.get('/events').then(r => setEvents(r.data));
  };
  useEffect(() => { load(); }, []);

  const applyTemplate = async (templateId) => {
    if (!applyEvent) { alert('Please select an event first'); return; }
    try {
      const { data } = await api.post(`/checklists/apply/${templateId}?event_id=${applyEvent}`);
      setApplyResult(data);
      setTimeout(() => setApplyResult(null), 5000);
    } catch (e) { console.error(e); }
  };

  const deleteTemplate = async (id) => {
    if (!window.confirm('Delete this template?')) return;
    await api.delete(`/checklists/templates/${id}`);
    load();
  };

  return (
    <div data-testid="checklists-page" className="animate-in">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="font-heading text-5xl uppercase leading-none">Checklists</h1>
          <p className="text-zinc-500 mt-1">Pre-built checklists for daily, weekly, monthly, and event-day operations</p>
        </div>
      </div>

      {/* Event Selector for Applying */}
      <div className="card-brutal p-4 mb-6">
        <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-2 block">Apply Checklist to Event</label>
        <select data-testid="checklist-event-select" value={applyEvent} onChange={e => setApplyEvent(e.target.value)} className="select-brutal max-w-md">
          <option value="">-- Select event --</option>
          {events.map(ev => <option key={ev._id} value={ev._id}>{ev.title}</option>)}
        </select>
      </div>

      {applyResult && (
        <div className="bg-green-50 border-2 border-green-500 p-4 mb-6 animate-in">
          <div className="flex items-center gap-2">
            <CheckCircle size={20} weight="fill" className="text-green-600" />
            <span className="font-semibold text-green-700">{applyResult.created} tasks created from checklist!</span>
          </div>
          <p className="text-sm text-green-600 mt-1">Tasks have been added to your event. View them in the Tasks page.</p>
        </div>
      )}

      {/* Templates Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {templates.map(template => (
          <div key={template._id} data-testid={`checklist-template-${template._id}`} className="card-brutal overflow-hidden">
            <div className="bg-zinc-950 text-white p-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <ClipboardText size={20} weight="bold" />
                <div>
                  <h3 className="font-heading text-xl uppercase">{template.name}</h3>
                  <span className={`inline-block mt-1 text-xs px-2 py-0.5 border font-mono uppercase ${TYPE_COLORS[template.type] || 'bg-zinc-100 text-zinc-700'}`}>
                    {TYPE_LABELS[template.type] || template.type}
                  </span>
                </div>
              </div>
              <span className="font-heading text-2xl text-zinc-400">{template.items?.length || 0}</span>
            </div>
            <div className="p-4">
              <ul className="space-y-2 mb-4">
                {(template.items || []).map((item, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm">
                    <div className={`w-2 h-2 mt-1.5 flex-shrink-0 ${item.priority === 'high' ? 'bg-[#DC2626]' : item.priority === 'medium' ? 'bg-[#F59E0B]' : 'bg-[#16A34A]'}`} />
                    <span>{item.title}</span>
                  </li>
                ))}
              </ul>
              <div className="flex gap-2">
                <button
                  data-testid={`apply-checklist-${template._id}`}
                  onClick={() => applyTemplate(template._id)}
                  disabled={!applyEvent}
                  className="btn-gold text-sm py-2 px-4 flex-1 flex items-center justify-center gap-2 disabled:opacity-40"
                >
                  <Play size={14} weight="fill" /> Apply to Event
                </button>
                <button
                  data-testid={`delete-checklist-${template._id}`}
                  onClick={() => deleteTemplate(template._id)}
                  className="border-2 border-zinc-950 px-3 py-2 hover:bg-red-50 hover:border-red-500 transition-colors"
                >
                  <Trash size={16} weight="bold" />
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {templates.length === 0 && (
        <div className="card-brutal p-12 text-center">
          <ClipboardText size={48} weight="bold" className="mx-auto mb-4 text-zinc-200" />
          <p className="font-heading text-3xl uppercase text-zinc-300 mb-2">No Templates</p>
          <p className="text-zinc-500">Templates will be seeded automatically on first load</p>
        </div>
      )}
    </div>
  );
}
