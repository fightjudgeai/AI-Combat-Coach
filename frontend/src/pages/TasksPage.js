import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Plus, Trash, X, CheckCircle, Circle, Clock } from '@phosphor-icons/react';

const PRIORITY_COLORS = { high: 'border-l-[#DC2626]', medium: 'border-l-[#F59E0B]', low: 'border-l-[#16A34A]' };

export default function TasksPage() {
  const { api } = useAuth();
  const [tasks, setTasks] = useState([]);
  const [events, setEvents] = useState([]);
  const [showModal, setShowModal] = useState(false);
  const [filter, setFilter] = useState('all');
  const [form, setForm] = useState(emptyForm());

  function emptyForm() {
    return { title: '', description: '', event_id: '', due_date: '', priority: 'medium', status: 'pending', recurrence: 'none', assigned_to: '' };
  }

  const load = () => {
    api.get('/tasks').then(r => setTasks(r.data));
    api.get('/events').then(r => setEvents(r.data));
  };
  useEffect(() => { load(); }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    await api.post('/tasks', { ...form, event_id: form.event_id || null, assigned_to: form.assigned_to || null });
    setShowModal(false);
    load();
  };

  const toggleStatus = async (id) => {
    await api.patch(`/tasks/${id}/status`);
    load();
  };

  const handleDelete = async (id) => {
    await api.delete(`/tasks/${id}`);
    load();
  };

  const filtered = filter === 'all' ? tasks : filter === 'completed' ? tasks.filter(t => t.status === 'completed') : tasks.filter(t => t.status === 'pending');
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const pendingCount = tasks.filter(t => t.status === 'pending').length;
  const completedCount = tasks.filter(t => t.status === 'completed').length;

  return (
    <div data-testid="tasks-page" className="animate-in">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="font-heading text-5xl uppercase leading-none">Tasks</h1>
          <p className="text-zinc-500 mt-1">{pendingCount} pending, {completedCount} completed</p>
        </div>
        <button data-testid="add-task-btn" onClick={() => { setForm(emptyForm()); setShowModal(true); }} className="btn-accent flex items-center gap-2">
          <Plus size={18} weight="bold" /> New Task
        </button>
      </div>

      {/* Filter tabs */}
      <div className="flex gap-2 mb-6">
        {['all', 'pending', 'completed'].map(f => (
          <button key={f} onClick={() => setFilter(f)} className={`font-heading uppercase text-lg px-4 py-2 border-2 transition-colors ${filter === f ? 'bg-zinc-950 text-white border-zinc-950' : 'border-zinc-300 text-zinc-500 hover:border-zinc-950'}`}>
            {f === 'all' ? `All (${tasks.length})` : f === 'pending' ? `Pending (${pendingCount})` : `Done (${completedCount})`}
          </button>
        ))}
      </div>

      {/* Task List */}
      {filtered.length === 0 ? (
        <div className="card-brutal p-12 text-center">
          <p className="font-heading text-3xl uppercase text-zinc-300 mb-2">No Tasks</p>
          <p className="text-zinc-500">Create tasks to stay on top of your events</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map(task => {
            const eventName = events.find(e => e._id === task.event_id)?.title;
            return (
              <div key={task._id} data-testid={`task-item-${task._id}`} className={`card-brutal border-l-4 ${PRIORITY_COLORS[task.priority] || 'border-l-zinc-300'} flex items-center gap-4 p-4`}>
                <button data-testid={`toggle-task-${task._id}`} onClick={() => toggleStatus(task._id)} className="flex-shrink-0">
                  {task.status === 'completed' ? (
                    <CheckCircle size={24} weight="fill" className="text-green-600" />
                  ) : (
                    <Circle size={24} weight="bold" className="text-zinc-300 hover:text-zinc-500" />
                  )}
                </button>
                <div className="flex-1 min-w-0">
                  <p className={`font-semibold ${task.status === 'completed' ? 'line-through text-zinc-400' : ''}`}>{task.title}</p>
                  {task.description && <p className="text-sm text-zinc-500 truncate">{task.description}</p>}
                  <div className="flex items-center gap-3 mt-1">
                    {eventName && <span className="font-mono text-xs uppercase text-zinc-400">{eventName}</span>}
                    {task.due_date && (
                      <span className="flex items-center gap-1 font-mono text-xs text-zinc-400">
                        <Clock size={12} /> {task.due_date}
                      </span>
                    )}
                    {task.recurrence !== 'none' && (
                      <span className="font-mono text-xs bg-zinc-100 px-2 py-0.5 uppercase">{task.recurrence}</span>
                    )}
                  </div>
                </div>
                <span className={`badge-status text-xs ${task.priority === 'high' ? 'border-red-500 text-red-600' : task.priority === 'low' ? 'border-green-500 text-green-600' : 'border-yellow-500 text-yellow-600'}`}>
                  {task.priority}
                </span>
                <button data-testid={`delete-task-${task._id}`} onClick={() => handleDelete(task._id)} className="p-2 hover:bg-red-50 hover:text-red-600 transition-colors flex-shrink-0">
                  <Trash size={16} weight="bold" />
                </button>
              </div>
            );
          })}
        </div>
      )}

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 modal-overlay flex items-center justify-center z-50 p-4" onClick={() => setShowModal(false)}>
          <div className="bg-white border-2 border-zinc-950 shadow-[8px_8px_0px_0px_rgba(9,9,11,1)] w-full max-w-lg animate-in" onClick={e => e.stopPropagation()}>
            <div className="bg-zinc-950 text-white p-4 flex items-center justify-between">
              <h2 className="font-heading text-2xl uppercase">New Task</h2>
              <button data-testid="close-task-modal" onClick={() => setShowModal(false)}><X size={20} className="text-white" /></button>
            </div>
            <form onSubmit={handleSubmit} className="p-6 space-y-4">
              <div>
                <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Task Title</label>
                <input data-testid="task-title-input" value={form.title} onChange={set('title')} className="input-brutal" placeholder="Book venue for weigh-ins" required />
              </div>
              <div>
                <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Description</label>
                <textarea data-testid="task-desc-input" value={form.description} onChange={set('description')} className="input-brutal h-20 resize-none" placeholder="Details..." />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Event (optional)</label>
                  <select data-testid="task-event-select" value={form.event_id} onChange={set('event_id')} className="select-brutal">
                    <option value="">No event</option>
                    {events.map(ev => <option key={ev._id} value={ev._id}>{ev.title}</option>)}
                  </select>
                </div>
                <div>
                  <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Due Date</label>
                  <input data-testid="task-due-input" type="date" value={form.due_date} onChange={set('due_date')} className="input-brutal" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Priority</label>
                  <select data-testid="task-priority-select" value={form.priority} onChange={set('priority')} className="select-brutal">
                    <option value="high">High</option>
                    <option value="medium">Medium</option>
                    <option value="low">Low</option>
                  </select>
                </div>
                <div>
                  <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-1 block">Recurrence</label>
                  <select data-testid="task-recurrence-select" value={form.recurrence} onChange={set('recurrence')} className="select-brutal">
                    <option value="none">None</option>
                    <option value="daily">Daily</option>
                    <option value="weekly">Weekly</option>
                    <option value="monthly">Monthly</option>
                  </select>
                </div>
              </div>
              <button data-testid="submit-task-btn" type="submit" className="btn-accent w-full text-center">Create Task</button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
