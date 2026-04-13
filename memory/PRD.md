# FightJudge Pro - Combat Sports Promoter SaaS

## Problem Statement
Enterprise-grade SaaS platform for combat sports promoters (MMA, boxing, kickboxing, grappling). Manages daily/weekly/monthly operations around events with AI-powered tools, Stripe ticketing, sponsor management, and real-time event-day command center.

## Architecture
- **Backend**: FastAPI + MongoDB (motor async) + JWT auth + bcrypt + OpenAI GPT via emergentintegrations + Stripe Checkout via emergentintegrations
- **Frontend**: React 19 + Tailwind CSS + Radix UI + Phosphor Icons + React Router + Recharts
- **Database**: MongoDB (collections: users, events, fighters, bouts, tasks, financials, sponsors, checklist_templates, payment_transactions, login_attempts)
- **AI**: OpenAI GPT via Emergent LLM Key (promo generation, matchup suggestions, smart reminders)
- **Payments**: Stripe Checkout via Emergent (ticket packages: General $65, VIP $150, Ringside $350, PPV $29.99)

## User Personas
- **Admin Promoter**: Full access to all modules, user management, financial oversight
- **Staff**: Event management, tasks, financials, sponsor coordination
- **Matchmaker**: Fighter roster, fight card builder, matchup suggestions

## Core Requirements (Static)
- [x] JWT Authentication with role-based access
- [x] Event Management CRUD with status tracking
- [x] Fighter Roster CRUD with weight class filtering
- [x] Fight Card Builder with bout matchups
- [x] Task Management with priority, recurrence, event linkage
- [x] Financial Tracking (revenue/expense with analytics)
- [x] AI Promo Description Generator
- [x] AI Fight Matchup Suggestions
- [x] Dashboard with key stats

## What's Been Implemented

### Phase 1 (2026-04-13) - MVP
- Full backend with 25+ API endpoints
- Auth, Events, Fighters, Fight Cards, Tasks, Financials, AI Tools
- Neo-brutalist UI with Bebas Neue typography
- Sample seed data (3 events, 6 fighters)

### Phase 2 (2026-04-13) - Expansion
- **Rebrand to FightJudge Pro**
- **Fight Night Live Dashboard** - Real-time event-day command center with bout status controls, live financial tally, ticket counts, auto-refresh
- **Sponsors Management** - Full CRUD with tier system (Platinum/Gold/Silver/Bronze), status tracking, contact info
- **Enhanced Checklists** - 4 seeded templates (Daily/Weekly/Monthly/Event Day) with apply-to-event functionality that auto-creates tasks
- **Revenue Analytics** - Charts (Pie: spending by category, Bar: monthly revenue vs expenses), per-event breakdown, 3-tab interface
- **Stripe Ticketing** - 4 ticket packages (General/VIP/Ringside/PPV), Stripe Checkout integration, payment status polling, purchase history
- **Smart AI Reminders** - AI scans event data for risk alerts, missing tasks, compliance issues, timeline recommendations
- **Enhanced Dashboard** - 8 stat cards, quick action buttons for Live/Checklists/AI

## Testing Status
- Backend: 45/45 tests passed (100%)
- Frontend: All core features working (95%+)
- Phase 2 features: All functional

## Prioritized Backlog
### P0 (Critical) - None remaining

### P1 (High)
- Google OAuth social login
- Mobile responsive sidebar (hamburger menu)
- Event detail page with linked bouts/tasks/financials
- Bout result recording with fighter record auto-update
- Custom checklist template creation UI

### P2 (Medium)
- Calendar view for events/tasks
- Export financials to CSV/PDF
- Email/SMS notifications (Twilio integration)
- Fighter profile photos (Cloudinary)
- Social media scheduler
- Dynamic ticket pricing based on sales velocity

### P3 (Low)
- Dark mode toggle
- Event poster/flyer AI generation
- Weight class rankings
- Historical analytics dashboard
- Live event overlays / stream integration
- Compliance AI (Texas TDLR filings)
- Crowd & ops AI (attendance prediction)
- Fan engagement tools (predictions, UGC challenges)
