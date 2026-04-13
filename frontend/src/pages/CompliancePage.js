import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { ShieldCheck, Warning, Plus, X, CheckCircle, Clock, FileText } from '@phosphor-icons/react';

const LICENSE_TYPES = ['promoter', 'matchmaker', 'referee', 'judge', 'fighter', 'physician'];
const SUSPENSION_TYPES = ['no_contact', 'no_sparring', 'medical_clearance_required'];

export default function CompliancePage() {
  const { api } = useAuth();
  const [dashboard, setDashboard] = useState(null);
  const [licenses, setLicenses] = useState([]);
  const [suspensions, setSuspensions] = useState([]);
  const [fighters, setFighters] = useState([]);
  const [tab, setTab] = useState('overview');
  const [showLicenseModal, setShowLicenseModal] = useState(false);
  const [showSuspensionModal, setShowSuspensionModal] = useState(false);
  const [licenseForm, setLicenseForm] = useState({ entity_type: 'promoter', entity_name: '', license_type: '', state: '', license_number: '', issue_date: '', expiry_date: '', status: 'active' });
  const [suspForm, setSuspForm] = useState({ fighter_id: '', fighter_name: '', type: 'no_contact', start_date: '', end_date: '', reason: '' });

  const load = () => {
    api.get('/compliance/dashboard').then(r => setDashboard(r.data)).catch(console.error);
    api.get('/licenses').then(r => setLicenses(r.data)).catch(console.error);
    api.get('/suspensions').then(r => setSuspensions(r.data)).catch(console.error);
    api.get('/fighters').then(r => setFighters(r.data)).catch(console.error);
  };
  useEffect(() => { load(); }, [api]);

  const createLicense = async (e) => { e.preventDefault(); await api.post('/licenses', licenseForm); setShowLicenseModal(false); load(); };
  const createSuspension = async (e) => {
    e.preventDefault();
    const fighter = fighters.find(f => f._id === suspForm.fighter_id);
    await api.post('/suspensions', { ...suspForm, fighter_name: fighter?.name || '' });
    setShowSuspensionModal(false); load();
  };
  const clearSuspension = async (id) => { await api.patch(`/suspensions/${id}/clear`); load(); };
  const deleteLicense = async (id) => { await api.delete(`/licenses/${id}`); load(); };
  const setL = (k) => (e) => setLicenseForm({ ...licenseForm, [k]: e.target.value });
  const setS = (k) => (e) => setSuspForm({ ...suspForm, [k]: e.target.value });

  return (
    <div data-testid="compliance-page" className="animate-in">
      <div className="flex items-center gap-4 mb-8">
        <div className="w-12 h-12 bg-zinc-950 flex items-center justify-center"><ShieldCheck weight="fill" className="text-white" size={28} /></div>
        <div><h1 className="font-heading text-5xl uppercase leading-none">Compliance</h1><p className="text-zinc-500">Licenses, medical suspensions & regulatory tracking</p></div>
      </div>

      {/* Alert Cards */}
      {dashboard && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
          <div className="card-brutal p-4 text-center"><p className="font-mono text-xs uppercase text-zinc-500">Total Licenses</p><p className="stat-value">{dashboard.total_licenses}</p></div>
          <div className={`card-brutal p-4 text-center ${dashboard.expired_licenses > 0 ? 'border-red-500' : ''}`}><p className="font-mono text-xs uppercase text-zinc-500">Expired</p><p className="stat-value text-red-600">{dashboard.expired_licenses}</p></div>
          <div className={`card-brutal p-4 text-center ${dashboard.expiring_count > 0 ? 'border-yellow-500' : ''}`}><p className="font-mono text-xs uppercase text-zinc-500">Expiring (30d)</p><p className="stat-value text-yellow-600">{dashboard.expiring_count}</p></div>
          <div className="card-brutal p-4 text-center"><p className="font-mono text-xs uppercase text-zinc-500">Active Suspensions</p><p className="stat-value text-[#DC2626]">{dashboard.active_suspensions}</p></div>
          <div className="card-brutal p-4 text-center"><p className="font-mono text-xs uppercase text-zinc-500">Unsigned Contracts</p><p className="stat-value">{dashboard.unsigned_contracts}</p></div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-2 mb-6">
        {['overview', 'licenses', 'suspensions'].map(t => (
          <button key={t} onClick={() => setTab(t)} className={`font-heading uppercase text-lg px-4 py-2 border-2 ${tab === t ? 'bg-zinc-950 text-white border-zinc-950' : 'border-zinc-300 text-zinc-500'}`}>
            {t === 'overview' ? 'Overview' : t === 'licenses' ? 'Licenses' : 'Medical Suspensions'}
          </button>
        ))}
      </div>

      {/* Overview */}
      {tab === 'overview' && dashboard?.expiring_licenses?.length > 0 && (
        <div className="card-brutal overflow-hidden mb-6">
          <div className="bg-yellow-500 text-zinc-950 p-4 flex items-center gap-2"><Warning size={20} weight="bold" /> <span className="font-heading text-lg uppercase">Expiring Licenses (Next 30 Days)</span></div>
          <div className="divide-y divide-zinc-100">
            {dashboard.expiring_licenses.map((l, i) => (
              <div key={i} className="p-4 flex items-center justify-between"><div><p className="font-semibold">{l.entity_name}</p><p className="text-sm text-zinc-500">{l.entity_type} | {l.state} | #{l.license_number}</p></div><span className="font-mono text-sm text-yellow-600">{l.expiry_date}</span></div>
            ))}
          </div>
        </div>
      )}

      {/* Licenses */}
      {tab === 'licenses' && (
        <>
          <div className="flex justify-end mb-4"><button data-testid="add-license-btn" onClick={() => setShowLicenseModal(true)} className="btn-accent flex items-center gap-2"><Plus size={16} weight="bold" /> Add License</button></div>
          <div className="card-brutal overflow-hidden">
            <table className="w-full"><thead><tr className="table-header-brutal"><th className="text-left p-4">Entity</th><th className="text-left p-4">Type</th><th className="text-left p-4">State</th><th className="text-left p-4">License #</th><th className="text-left p-4">Expiry</th><th className="text-center p-4">Status</th><th className="text-right p-4">Action</th></tr></thead>
              <tbody className="divide-y-2 divide-zinc-100">
                {licenses.map(l => (
                  <tr key={l._id} className="hover:bg-zinc-50">
                    <td className="p-4 font-semibold">{l.entity_name}</td><td className="p-4"><span className="badge-weight">{l.entity_type}</span></td>
                    <td className="p-4 text-sm">{l.state || '-'}</td><td className="p-4 font-mono text-sm">{l.license_number || '-'}</td>
                    <td className="p-4 font-mono text-sm">{l.expiry_date || '-'}</td>
                    <td className="p-4 text-center"><span className={`badge-status text-xs ${l.status === 'active' ? 'border-green-600 text-green-700' : 'border-red-600 text-red-700'}`}>{l.status}</span></td>
                    <td className="p-4 text-right"><button onClick={() => deleteLicense(l._id)} className="p-2 hover:text-red-600"><X size={14} /></button></td>
                  </tr>
                ))}
              </tbody>
            </table>
            {licenses.length === 0 && <div className="p-8 text-center text-zinc-400">No licenses tracked yet</div>}
          </div>
        </>
      )}

      {/* Suspensions */}
      {tab === 'suspensions' && (
        <>
          <div className="flex justify-end mb-4"><button data-testid="add-suspension-btn" onClick={() => setShowSuspensionModal(true)} className="btn-accent flex items-center gap-2"><Plus size={16} weight="bold" /> Add Suspension</button></div>
          <div className="space-y-3">
            {suspensions.map(s => (
              <div key={s._id} data-testid={`suspension-${s._id}`} className={`card-brutal p-4 border-l-4 ${s.cleared ? 'border-l-green-500' : 'border-l-[#DC2626]'} flex items-center justify-between`}>
                <div>
                  <p className="font-semibold">{s.fighter_name || 'Unknown Fighter'}</p>
                  <p className="text-sm text-zinc-500">{s.type.replace(/_/g, ' ')} | {s.start_date} to {s.end_date}</p>
                  {s.reason && <p className="text-xs text-zinc-400 mt-1">{s.reason}</p>}
                </div>
                {s.cleared ? (
                  <span className="flex items-center gap-1 text-green-600 font-mono text-xs"><CheckCircle size={14} weight="fill" /> Cleared {s.cleared_date?.slice(0, 10)}</span>
                ) : (
                  <button onClick={() => clearSuspension(s._id)} className="btn-primary text-sm py-2 px-4">Clear Suspension</button>
                )}
              </div>
            ))}
            {suspensions.length === 0 && <div className="card-brutal p-12 text-center text-zinc-400">No medical suspensions</div>}
          </div>
        </>
      )}

      {/* License Modal */}
      {showLicenseModal && (
        <div className="fixed inset-0 modal-overlay flex items-center justify-center z-50 p-4" onClick={() => setShowLicenseModal(false)}>
          <div className="bg-white border-2 border-zinc-950 shadow-[8px_8px_0px_0px_rgba(9,9,11,1)] w-full max-w-lg animate-in" onClick={e => e.stopPropagation()}>
            <div className="bg-zinc-950 text-white p-4 flex items-center justify-between"><h2 className="font-heading text-2xl uppercase">Add License</h2><button onClick={() => setShowLicenseModal(false)}><X size={20} className="text-white" /></button></div>
            <form onSubmit={createLicense} className="p-6 space-y-4">
              <div className="grid grid-cols-2 gap-4"><div><label className="font-mono text-xs uppercase text-zinc-500 mb-1 block">Entity Type</label><select value={licenseForm.entity_type} onChange={setL('entity_type')} className="select-brutal">{LICENSE_TYPES.map(t => <option key={t} value={t}>{t}</option>)}</select></div><div><label className="font-mono text-xs uppercase text-zinc-500 mb-1 block">Entity Name</label><input value={licenseForm.entity_name} onChange={setL('entity_name')} className="input-brutal" required /></div></div>
              <div className="grid grid-cols-2 gap-4"><div><label className="font-mono text-xs uppercase text-zinc-500 mb-1 block">State</label><input value={licenseForm.state} onChange={setL('state')} className="input-brutal" /></div><div><label className="font-mono text-xs uppercase text-zinc-500 mb-1 block">License #</label><input value={licenseForm.license_number} onChange={setL('license_number')} className="input-brutal" /></div></div>
              <div className="grid grid-cols-2 gap-4"><div><label className="font-mono text-xs uppercase text-zinc-500 mb-1 block">Issue Date</label><input type="date" value={licenseForm.issue_date} onChange={setL('issue_date')} className="input-brutal" /></div><div><label className="font-mono text-xs uppercase text-zinc-500 mb-1 block">Expiry Date</label><input type="date" value={licenseForm.expiry_date} onChange={setL('expiry_date')} className="input-brutal" /></div></div>
              <button type="submit" className="btn-accent w-full text-center">Add License</button>
            </form>
          </div>
        </div>
      )}

      {/* Suspension Modal */}
      {showSuspensionModal && (
        <div className="fixed inset-0 modal-overlay flex items-center justify-center z-50 p-4" onClick={() => setShowSuspensionModal(false)}>
          <div className="bg-white border-2 border-zinc-950 shadow-[8px_8px_0px_0px_rgba(9,9,11,1)] w-full max-w-lg animate-in" onClick={e => e.stopPropagation()}>
            <div className="bg-zinc-950 text-white p-4 flex items-center justify-between"><h2 className="font-heading text-2xl uppercase">Add Suspension</h2><button onClick={() => setShowSuspensionModal(false)}><X size={20} className="text-white" /></button></div>
            <form onSubmit={createSuspension} className="p-6 space-y-4">
              <div><label className="font-mono text-xs uppercase text-zinc-500 mb-1 block">Fighter</label><select value={suspForm.fighter_id} onChange={setS('fighter_id')} className="select-brutal" required><option value="">Select fighter</option>{fighters.map(f => <option key={f._id} value={f._id}>{f.name}</option>)}</select></div>
              <div className="grid grid-cols-3 gap-4"><div><label className="font-mono text-xs uppercase text-zinc-500 mb-1 block">Type</label><select value={suspForm.type} onChange={setS('type')} className="select-brutal">{SUSPENSION_TYPES.map(t => <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>)}</select></div><div><label className="font-mono text-xs uppercase text-zinc-500 mb-1 block">Start</label><input type="date" value={suspForm.start_date} onChange={setS('start_date')} className="input-brutal" required /></div><div><label className="font-mono text-xs uppercase text-zinc-500 mb-1 block">End</label><input type="date" value={suspForm.end_date} onChange={setS('end_date')} className="input-brutal" required /></div></div>
              <div><label className="font-mono text-xs uppercase text-zinc-500 mb-1 block">Reason</label><input value={suspForm.reason} onChange={setS('reason')} className="input-brutal" /></div>
              <button type="submit" className="btn-accent w-full text-center">Add Suspension</button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
