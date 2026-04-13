import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Lightning, House, UsersFour, Sword, ChatCircle, SignOut } from '@phosphor-icons/react';

const navItems = [
  { to: '/coach-portal', icon: House, label: 'Dashboard', end: true },
  { to: '/coach-portal/fighters', icon: UsersFour, label: 'My Fighters' },
  { to: '/coach-portal/bouts', icon: Sword, label: 'Upcoming Bouts' },
  { to: '/coach-portal/messages', icon: ChatCircle, label: 'Messages' },
];

export default function CoachPortalLayout({ children }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <div className="flex min-h-screen bg-[#0a1628]">
      <aside data-testid="coach-sidebar" className="w-60 bg-[#0d1f3c] border-r border-[#1a3a6b] flex flex-col fixed h-screen z-40">
        <div className="p-4 border-b border-[#1a3a6b]">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-[#D4AF37] flex items-center justify-center flex-shrink-0">
              <Lightning weight="fill" className="text-[#0d1f3c]" size={18} />
            </div>
            <div>
              <span className="font-heading text-lg uppercase tracking-wide block leading-none text-white">Coach</span>
              <span className="font-mono text-[9px] uppercase tracking-widest text-[#D4AF37]">Corner Portal</span>
            </div>
          </div>
        </div>

        <nav className="flex-1 py-4">
          {navItems.map(item => (
            <NavLink key={item.to} to={item.to} end={item.end}
              data-testid={`cp-nav-${item.label.toLowerCase().replace(/\s/g, '-')}`}
              className={({ isActive }) => `flex items-center gap-3 px-4 py-2.5 text-sm transition-all border-l-3 ${isActive ? 'text-white bg-[#1a3a6b] border-l-[#D4AF37] font-semibold' : 'text-blue-300/60 hover:text-white hover:bg-[#1a3a6b]/50 border-l-transparent'}`}>
              <item.icon size={18} weight="bold" />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-[#1a3a6b] p-4">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-8 h-8 bg-[#D4AF37] flex items-center justify-center font-heading text-sm text-[#0d1f3c]">{user?.name?.charAt(0)?.toUpperCase() || 'C'}</div>
            <div className="flex-1 min-w-0">
              <p className="font-semibold text-sm text-white truncate">{user?.name || 'Coach'}</p>
              <p className="text-[10px] text-blue-400/50 font-mono uppercase">{user?.gym || 'Coach'}</p>
            </div>
          </div>
          <button data-testid="cp-logout" onClick={async () => { await logout(); navigate('/login'); }} className="flex items-center gap-2 text-blue-400/50 hover:text-[#D4AF37] text-xs font-medium w-full transition-colors">
            <SignOut size={14} weight="bold" /> Sign Out
          </button>
        </div>
      </aside>
      <main className="flex-1 ml-60 bg-[#0a1628] min-h-screen">
        <div className="p-6 md:p-8">{children}</div>
      </main>
    </div>
  );
}
