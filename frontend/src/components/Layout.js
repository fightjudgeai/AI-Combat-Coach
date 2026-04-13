import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import {
  Lightning, House, CalendarBlank, UsersFour, Sword,
  ListChecks, CurrencyDollar, SignOut, Sparkle, Gear
} from '@phosphor-icons/react';

const navItems = [
  { to: '/dashboard', icon: House, label: 'Dashboard' },
  { to: '/events', icon: CalendarBlank, label: 'Events' },
  { to: '/fighters', icon: UsersFour, label: 'Fighters' },
  { to: '/fight-cards', icon: Sword, label: 'Fight Cards' },
  { to: '/tasks', icon: ListChecks, label: 'Tasks' },
  { to: '/finance', icon: CurrencyDollar, label: 'Financials' },
  { to: '/ai-tools', icon: Sparkle, label: 'AI Tools' },
];

export default function Layout({ children }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <div className="flex min-h-screen bg-[#F4F4F5]">
      {/* Sidebar */}
      <aside data-testid="sidebar" className="w-64 bg-white border-r-2 border-zinc-950 flex flex-col fixed h-screen z-40">
        <div className="p-5 border-b-2 border-zinc-950">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-[#DC2626] flex items-center justify-center flex-shrink-0">
              <Lightning weight="fill" className="text-white" size={20} />
            </div>
            <span className="font-heading text-2xl uppercase tracking-wide">FightPromo</span>
          </div>
        </div>

        <nav className="flex-1 py-4 overflow-y-auto">
          {navItems.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              data-testid={`nav-${item.label.toLowerCase().replace(/\s/g, '-')}`}
              className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}
            >
              <item.icon size={20} weight="bold" />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="border-t-2 border-zinc-950 p-4">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-8 h-8 bg-zinc-200 flex items-center justify-center font-heading text-sm">
              {user?.name?.charAt(0)?.toUpperCase() || 'U'}
            </div>
            <div className="flex-1 min-w-0">
              <p className="font-semibold text-sm truncate">{user?.name || 'User'}</p>
              <p className="text-xs text-zinc-500 font-mono uppercase">{user?.role || 'staff'}</p>
            </div>
          </div>
          <button
            data-testid="logout-button"
            onClick={handleLogout}
            className="flex items-center gap-2 text-zinc-500 hover:text-[#DC2626] text-sm font-medium w-full transition-colors"
          >
            <SignOut size={16} weight="bold" />
            Sign Out
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 ml-64">
        <div className="p-6 md:p-8 lg:p-10">
          {children}
        </div>
      </main>
    </div>
  );
}
