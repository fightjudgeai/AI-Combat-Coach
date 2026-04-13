import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { CheckCircle } from '@phosphor-icons/react';

export default function FighterProfile() {
  const { api } = useAuth();
  const [profile, setProfile] = useState(null);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({});
  const [saved, setSaved] = useState(false);

  useEffect(() => { api.get('/fighter-portal/profile').then(r => { setProfile(r.data); setForm(r.data); }).catch(console.error); }, [api]);

  const handleSave = async (e) => {
    e.preventDefault();
    const { data } = await api.put('/fighter-portal/profile', {
      name: form.name, nickname: form.nickname, weight_class: form.weight_class,
      age: parseInt(form.age) || 0, height: form.height, reach: form.reach,
      stance: form.stance, gym: form.gym, phone: form.phone || '',
      bio: form.bio || '', emergency_contact: form.emergency_contact || '', emergency_phone: form.emergency_phone || ''
    });
    setProfile(data); setEditing(false); setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  };

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  if (!profile) return <div className="flex items-center justify-center h-64"><div className="w-8 h-8 bg-[#DC2626] animate-pulse" /></div>;

  return (
    <div data-testid="fighter-profile-page" className="animate-in">
      <div className="flex items-center justify-between mb-6">
        <h1 className="font-heading text-4xl text-white uppercase">My Profile</h1>
        {!editing ? (
          <button data-testid="edit-profile-btn" onClick={() => setEditing(true)} className="bg-[#DC2626] text-white font-heading uppercase px-4 py-2 text-sm hover:bg-red-700 transition-colors">Edit Profile</button>
        ) : (
          <button onClick={() => setEditing(false)} className="bg-zinc-800 text-zinc-400 font-heading uppercase px-4 py-2 text-sm">Cancel</button>
        )}
      </div>
      {saved && <div className="bg-green-900/30 border border-green-800 p-3 mb-4 flex items-center gap-2 text-green-400"><CheckCircle size={16} weight="fill" /> Profile updated successfully</div>}

      <form onSubmit={handleSave}>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Basic Info */}
          <div className="bg-zinc-900 border border-zinc-800 p-5">
            <h3 className="font-heading text-lg text-[#DC2626] uppercase mb-4">Fighter Info</h3>
            {[
              { k: 'name', label: 'Full Name' }, { k: 'nickname', label: 'Nickname' },
              { k: 'weight_class', label: 'Weight Class', type: 'select', options: ['Strawweight','Flyweight','Bantamweight','Featherweight','Lightweight','Welterweight','Middleweight','Light Heavyweight','Heavyweight'] },
              { k: 'stance', label: 'Stance', type: 'select', options: ['orthodox','southpaw','switch'] },
              { k: 'gym', label: 'Gym / Team' },
            ].map(f => (
              <div key={f.k} className="mb-3">
                <label className="font-mono text-[10px] uppercase tracking-widest text-zinc-500 mb-1 block">{f.label}</label>
                {editing ? (
                  f.type === 'select' ? <select value={form[f.k] || ''} onChange={set(f.k)} className="w-full bg-zinc-800 border border-zinc-700 text-white p-2 text-sm outline-none focus:border-[#DC2626]">{f.options.map(o => <option key={o} value={o}>{o}</option>)}</select>
                  : <input value={form[f.k] || ''} onChange={set(f.k)} className="w-full bg-zinc-800 border border-zinc-700 text-white p-2 text-sm outline-none focus:border-[#DC2626]" />
                ) : <p className="text-white text-sm">{profile[f.k] || '-'}</p>}
              </div>
            ))}
          </div>

          {/* Physical Stats */}
          <div className="bg-zinc-900 border border-zinc-800 p-5">
            <h3 className="font-heading text-lg text-[#D4AF37] uppercase mb-4">Physical Stats</h3>
            {[
              { k: 'age', label: 'Age', type: 'number' }, { k: 'height', label: 'Height' }, { k: 'reach', label: 'Reach' },
            ].map(f => (
              <div key={f.k} className="mb-3">
                <label className="font-mono text-[10px] uppercase tracking-widest text-zinc-500 mb-1 block">{f.label}</label>
                {editing ? <input type={f.type || 'text'} value={form[f.k] || ''} onChange={set(f.k)} className="w-full bg-zinc-800 border border-zinc-700 text-white p-2 text-sm outline-none focus:border-[#DC2626]" /> : <p className="text-white text-sm">{profile[f.k] || '-'}</p>}
              </div>
            ))}
            <h3 className="font-heading text-lg text-zinc-500 uppercase mt-6 mb-4">Record</h3>
            <div className="grid grid-cols-3 gap-4 text-center">
              <div><p className="font-heading text-3xl text-green-400">{profile.wins || 0}</p><p className="font-mono text-xs text-zinc-500">Wins</p></div>
              <div><p className="font-heading text-3xl text-red-400">{profile.losses || 0}</p><p className="font-mono text-xs text-zinc-500">Losses</p></div>
              <div><p className="font-heading text-3xl text-zinc-400">{profile.draws || 0}</p><p className="font-mono text-xs text-zinc-500">Draws</p></div>
            </div>
          </div>

          {/* Contact & Emergency */}
          <div className="bg-zinc-900 border border-zinc-800 p-5 md:col-span-2">
            <h3 className="font-heading text-lg text-zinc-400 uppercase mb-4">Contact & Emergency</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {[
                { k: 'phone', label: 'Phone' }, { k: 'emergency_contact', label: 'Emergency Contact' }, { k: 'emergency_phone', label: 'Emergency Phone' },
              ].map(f => (
                <div key={f.k}>
                  <label className="font-mono text-[10px] uppercase tracking-widest text-zinc-500 mb-1 block">{f.label}</label>
                  {editing ? <input value={form[f.k] || ''} onChange={set(f.k)} className="w-full bg-zinc-800 border border-zinc-700 text-white p-2 text-sm outline-none focus:border-[#DC2626]" /> : <p className="text-white text-sm">{profile[f.k] || '-'}</p>}
                </div>
              ))}
            </div>
            {editing && (
              <div className="mt-4"><label className="font-mono text-[10px] uppercase tracking-widest text-zinc-500 mb-1 block">Bio</label>
                <textarea value={form.bio || ''} onChange={set('bio')} className="w-full bg-zinc-800 border border-zinc-700 text-white p-2 text-sm outline-none focus:border-[#DC2626] h-20 resize-none" />
              </div>
            )}
            {!editing && profile.bio && <div className="mt-4"><label className="font-mono text-[10px] uppercase tracking-widest text-zinc-500 mb-1 block">Bio</label><p className="text-white text-sm">{profile.bio}</p></div>}
          </div>
        </div>
        {editing && <button data-testid="save-profile-btn" type="submit" className="mt-6 bg-[#DC2626] text-white font-heading uppercase text-xl px-8 py-3 hover:bg-red-700 transition-colors">Save Profile</button>}
      </form>
    </div>
  );
}
