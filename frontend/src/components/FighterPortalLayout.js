import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Lightning, House, Sword, FirstAid, FileText, CurrencyDollar, UserCircle, ChatCircle, SignOut } from '@phosphor-icons/react';

const navItems = [
  { to: '/fighter-portal', icon: House, label: 'Dashboard', end: true },
  { to: '/fighter-portal/bouts', icon: Sword, label: 'My Bouts' },
  { to: '/fighter-portal/medicals', icon: FirstAid, label: 'Medical Status' },
  { to: '/fighter-portal/contracts', icon: FileText, label: 'Contracts' },
  { to: '/fighter-portal/payments', icon: CurrencyDollar, label: 'Payments' },
  { to: '/fighter-portal/profile', icon: UserCircle, label: 'My Profile' },
  { to: '/fighter-portal/messages', icon: ChatCircle, label: 'Messages' },
];

export default function FighterPortalLayout({ children }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <div className="flex min-h-screen bg-zinc-950">
      {/* Fighter Portal Sidebar - Dark Theme */}
      <aside data-testid="fighter-sidebar" className="w-60 bg-zinc-900 border-r border-zinc-800 flex flex-col fixed h-screen z-40">
        <div className="p-4 border-b border-zinc-800">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-[#DC2626] flex items-center justify-center flex-shrink-0">
              <Lightning weight="fill" className="text-white" size={18} />
            </div>
            <div>
              <span className="font-heading text-lg uppercase tracking-wide block leading-none text-white">Fighter</span>
              <span className="font-mono text-[9px] uppercase tracking-widest text-[#D4AF37]">Portal</span>
            </div>
          </div>
        </div>

        <nav className="flex-1 py-4 overflow-y-auto">
          {navItems.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              data-testid={`fp-nav-${item.label.toLowerCase().replace(/\s/g, '-')}`}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-2.5 text-sm transition-all border-l-3 ${
                  isActive
                    ? 'text-white bg-zinc-800 border-l-[#DC2626] font-semibold'
                    : 'text-zinc-400 hover:text-white hover:bg-zinc-800/50 border-l-transparent'
                }`
              }
            >
              <item.icon size={18} weight="bold" />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-zinc-800 p-4">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-8 h-8 bg-[#DC2626] flex items-center justify-center font-heading text-sm text-white">
              {user?.name?.charAt(0)?.toUpperCase() || 'F'}
            </div>
            <div className="flex-1 min-w-0">
              <p className="font-semibold text-sm text-white truncate">{user?.name || 'Fighter'}</p>
              <p className="text-[10px] text-zinc-500 font-mono uppercase">Fighter</p>
            </div>
          </div>
          <button data-testid="fp-logout" onClick={async () => { await logout(); navigate('/login'); }} className="flex items-center gap-2 text-zinc-500 hover:text-[#DC2626] text-xs font-medium w-full transition-colors">
            <SignOut size={14} weight="bold" /> Sign Out
          </button>
        </div>
      </aside>

      <main className="flex-1 ml-60 bg-zinc-950 min-h-screen">
        <div className="p-6 md:p-8">{children}</div>
      </main>
    </div>
  );
}
