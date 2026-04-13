import React, { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Navigate } from 'react-router-dom';
import { Lightning, Eye, EyeSlash } from '@phosphor-icons/react';

const AUTH_HERO = "https://images.unsplash.com/photo-1720731052635-c6de1beca7f9?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NTYxOTJ8MHwxfHNlYXJjaHw0fHxtbWElMjBmaWdodGVyJTIwcG9ydHJhaXR8ZW58MHx8fHwxNzc2MDQ0MDY4fDA&ixlib=rb-4.1.0&q=85";

export default function RegisterPage() {
  const { user, register, loading } = useAuth();
  const [form, setForm] = useState({ name: '', email: '', password: '', role: 'staff' });
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [showPw, setShowPw] = useState(false);

  if (loading) return null;
  if (user) return <Navigate to="/dashboard" />;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    if (form.password.length < 6) { setError('Password must be at least 6 characters'); return; }
    setSubmitting(true);
    const result = await register(form.email, form.password, form.name, form.role);
    if (!result.success) setError(result.error);
    setSubmitting(false);
  };

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 min-h-screen">
      <div className="hidden lg:block relative overflow-hidden bg-black">
        <img src={AUTH_HERO} alt="Fighter" className="absolute inset-0 w-full h-full object-cover opacity-60" />
        <div className="absolute inset-0 bg-gradient-to-t from-black via-black/40 to-transparent" />
        <div className="absolute bottom-12 left-12 right-12">
          <h1 className="font-heading text-6xl text-white uppercase leading-none mb-3">Join The<br/>Promotion<br/>Team</h1>
          <p className="text-zinc-400 text-lg max-w-md">Create your account and start managing combat sports events like a pro.</p>
        </div>
      </div>

      <div className="flex items-center justify-center p-8 lg:p-16 bg-white">
        <div className="w-full max-w-md animate-in">
          <div className="flex items-center gap-3 mb-10">
            <div className="w-10 h-10 bg-[#DC2626] flex items-center justify-center">
              <Lightning weight="fill" className="text-white" size={24} />
            </div>
            <div>
              <span className="font-heading text-2xl uppercase tracking-wide block leading-none">FightJudge</span>
              <span className="font-mono text-[10px] uppercase tracking-widest text-[#D4AF37]">Pro</span>
            </div>
          </div>

          <h2 className="font-heading text-4xl uppercase mb-2">Create Account</h2>
          <p className="text-zinc-500 mb-8">Set up your promoter profile</p>

          {error && (
            <div data-testid="register-error" className="bg-red-50 border-2 border-red-500 p-3 mb-6 text-red-700 text-sm font-medium">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-2 block">Full Name</label>
              <input data-testid="register-name-input" value={form.name} onChange={set('name')} className="input-brutal" placeholder="John Doe" required />
            </div>
            <div>
              <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-2 block">Email</label>
              <input data-testid="register-email-input" type="email" value={form.email} onChange={set('email')} className="input-brutal" placeholder="john@promotions.com" required />
            </div>
            <div>
              <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-2 block">Password</label>
              <div className="relative">
                <input data-testid="register-password-input" type={showPw ? "text" : "password"} value={form.password} onChange={set('password')} className="input-brutal pr-12" placeholder="Min 6 characters" required />
                <button type="button" onClick={() => setShowPw(!showPw)} className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-zinc-700">
                  {showPw ? <EyeSlash size={20} /> : <Eye size={20} />}
                </button>
              </div>
            </div>
            <div>
              <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-2 block">Role</label>
              <select data-testid="register-role-select" value={form.role} onChange={set('role')} className="select-brutal">
                <option value="staff">Staff</option>
                <option value="matchmaker">Matchmaker</option>
              </select>
            </div>
            <button data-testid="register-submit-button" type="submit" disabled={submitting} className="btn-accent w-full text-center disabled:opacity-50">
              {submitting ? "Creating account..." : "Join the Team"}
            </button>
          </form>

          <p className="mt-8 text-center text-zinc-500">
            Already have an account?{' '}
            <a href="/login" data-testid="go-to-login" className="text-[#DC2626] font-semibold hover:underline">Sign In</a>
          </p>
        </div>
      </div>
    </div>
  );
}
