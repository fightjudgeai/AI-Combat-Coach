import React, { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Navigate } from 'react-router-dom';
import { Eye, EyeSlash, Lightning } from '@phosphor-icons/react';

const AUTH_HERO = "https://images.unsplash.com/photo-1720731052635-c6de1beca7f9?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NTYxOTJ8MHwxfHNlYXJjaHw0fHxtbWElMjBmaWdodGVyJTIwcG9ydHJhaXR8ZW58MHx8fHwxNzc2MDQ0MDY4fDA&ixlib=rb-4.1.0&q=85";

export default function LoginPage() {
  const { user, login, loading } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [showPw, setShowPw] = useState(false);

  if (loading) return <LoadingScreen />;
  if (user) return <Navigate to={user.role === 'fighter' ? '/fighter-portal' : user.role === 'coach' ? '/coach-portal' : '/dashboard'} />;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    const result = await login(email, password);
    if (!result.success) setError(result.error);
    setSubmitting(false);
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 min-h-screen">
      {/* Left - Hero Image */}
      <div className="hidden lg:block relative overflow-hidden bg-black">
        <img src={AUTH_HERO} alt="Fighter" className="absolute inset-0 w-full h-full object-cover opacity-60" />
        <div className="absolute inset-0 bg-gradient-to-t from-black via-black/40 to-transparent" />
        <div className="absolute bottom-12 left-12 right-12">
          <h1 className="font-heading text-6xl text-white uppercase leading-none mb-3">Fight<br/>Promoter<br/>Command Center</h1>
          <p className="text-zinc-400 text-lg max-w-md">Manage events, fighters, cards, and finances — all from one platform built for combat sports.</p>
        </div>
      </div>

      {/* Right - Login Form */}
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

          <h2 className="font-heading text-4xl uppercase mb-2">Sign In</h2>
          <p className="text-zinc-500 mb-8">Enter your credentials to access your command center</p>

          {error && (
            <div data-testid="login-error" className="bg-red-50 border-2 border-red-500 p-3 mb-6 text-red-700 text-sm font-medium">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-2 block">Email</label>
              <input
                data-testid="login-email-input"
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                className="input-brutal"
                placeholder="admin@fightpromo.com"
                required
              />
            </div>
            <div>
              <label className="font-mono text-xs uppercase tracking-widest text-zinc-500 mb-2 block">Password</label>
              <div className="relative">
                <input
                  data-testid="login-password-input"
                  type={showPw ? "text" : "password"}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  className="input-brutal pr-12"
                  placeholder="Enter password"
                  required
                />
                <button type="button" onClick={() => setShowPw(!showPw)} className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-zinc-700">
                  {showPw ? <EyeSlash size={20} /> : <Eye size={20} />}
                </button>
              </div>
            </div>
            <button
              data-testid="login-submit-button"
              type="submit"
              disabled={submitting}
              className="btn-accent w-full text-center disabled:opacity-50"
            >
              {submitting ? "Signing in..." : "Enter the Ring"}
            </button>
          </form>

          <p className="mt-8 text-center text-zinc-500">
            Don't have an account?{' '}
            <a href="/register" data-testid="go-to-register" className="text-[#DC2626] font-semibold hover:underline">Register</a>
          </p>
          <p className="mt-2 text-center">
            <a href="/register?role=fighter" data-testid="go-to-fighter-register" className="text-[#D4AF37] font-semibold text-sm hover:underline">Fighter? Register for Portal</a>
          </p>
        </div>
      </div>
    </div>
  );
}

function LoadingScreen() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-white">
      <div className="text-center">
        <div className="w-12 h-12 bg-[#DC2626] mx-auto mb-4 animate-pulse" />
        <p className="font-heading text-2xl uppercase">Loading...</p>
      </div>
    </div>
  );
}
