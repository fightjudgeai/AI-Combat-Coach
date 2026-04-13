import React, { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import {
  Lightning, House, CalendarBlank, UsersFour, Sword,
  ListChecks, CurrencyDollar, SignOut, Sparkle, Handshake,
  ClipboardText, Broadcast, Ticket, Gavel, BuildingOffice,
  ShieldCheck, ChatCircle, FileText, Megaphone, CaretDown, CaretRight
} from '@phosphor-icons/react';

const sections = [
  { label: 'Overview', items: [
    { to: '/dashboard', icon: House, label: 'Dashboard' },
  ]},
  { label: 'Events', items: [
    { to: '/events', icon: CalendarBlank, label: 'Events' },
    { to: '/fight-cards', icon: Sword, label: 'Fight Cards' },
    { to: '/live', icon: Broadcast, label: 'Fight Night Live' },
  ]},
  { label: 'People', items: [
    { to: '/fighters', icon: UsersFour, label: 'Fighters' },
    { to: '/officials', icon: Gavel, label: 'Officials & Staff' },
  ]},
  { label: 'Operations', items: [
    { to: '/tasks', icon: ListChecks, label: 'Tasks' },
    { to: '/checklists', icon: ClipboardText, label: 'Checklists' },
    { to: '/venues', icon: BuildingOffice, label: 'Venues' },
    { to: '/compliance', icon: ShieldCheck, label: 'Compliance' },
  ]},
  { label: 'Business', items: [
    { to: '/sponsors', icon: Handshake, label: 'Sponsors' },
    { to: '/tickets', icon: Ticket, label: 'Ticketing' },
    { to: '/finance', icon: CurrencyDollar, label: 'Financials' },
    { to: '/marketing', icon: Megaphone, label: 'Marketing' },
  ]},
  { label: 'Tools', items: [
    { to: '/ai-tools', icon: Sparkle, label: 'AI Tools' },
    { to: '/messages', icon: ChatCircle, label: 'Messages' },
    { to: '/documents', icon: FileText, label: 'Documents' },
  ]},
];

export default function Layout({ children }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [collapsed, setCollapsed] = useState({});

  const toggle = (label) => setCollapsed(prev => ({ ...prev, [label]: !prev[label] }));

  return (
    <div className="flex min-h-screen bg-[#F4F4F5]">
      <aside data-testid="sidebar" className="w-60 bg-white border-r-2 border-zinc-950 flex flex-col fixed h-screen z-40">
        <div className="p-4 border-b-2 border-zinc-950">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-[#DC2626] flex items-center justify-center flex-shrink-0">
              <Lightning weight="fill" className="text-white" size={18} />
            </div>
            <div>
              <span className="font-heading text-lg uppercase tracking-wide block leading-none">FightJudge</span>
              <span className="font-mono text-[9px] uppercase tracking-widest text-[#D4AF37]">Pro</span>
            </div>
          </div>
        </div>

        <nav className="flex-1 py-2 overflow-y-auto">
          {sections.map(section => (
            <div key={section.label}>
              <button onClick={() => toggle(section.label)} className="w-full flex items-center justify-between px-4 py-1.5 text-left">
                <span className="font-mono text-[10px] uppercase tracking-[0.15em] text-zinc-400">{section.label}</span>
                {collapsed[section.label] ? <CaretRight size={10} className="text-zinc-400" /> : <CaretDown size={10} className="text-zinc-400" />}
              </button>
              {!collapsed[section.label] && section.items.map(item => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  data-testid={`nav-${item.label.toLowerCase().replace(/[\s&]/g, '-')}`}
                  className={({ isActive }) => `sidebar-link text-[13px] py-1.5 ${isActive ? 'active' : ''}`}
                >
                  <item.icon size={16} weight="bold" />
                  <span>{item.label}</span>
                </NavLink>
              ))}
            </div>
          ))}
        </nav>

        <div className="border-t-2 border-zinc-950 p-3">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-7 h-7 bg-zinc-200 flex items-center justify-center font-heading text-xs">
              {user?.name?.charAt(0)?.toUpperCase() || 'U'}
            </div>
            <div className="flex-1 min-w-0">
              <p className="font-semibold text-xs truncate">{user?.name || 'User'}</p>
              <p className="text-[10px] text-zinc-500 font-mono uppercase">{user?.role || 'staff'}</p>
            </div>
          </div>
          <button data-testid="logout-button" onClick={async () => { await logout(); navigate('/login'); }} className="flex items-center gap-2 text-zinc-500 hover:text-[#DC2626] text-xs font-medium w-full transition-colors">
            <SignOut size={14} weight="bold" /> Sign Out
          </button>
        </div>
      </aside>
      <main className="flex-1 ml-60">
        <div className="p-6 md:p-8">{children}</div>
      </main>
    </div>
  );
}
