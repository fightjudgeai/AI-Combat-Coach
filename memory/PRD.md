# FightJudge Pro - Combat Sports Promoter SaaS

## Problem Statement
Enterprise-grade SaaS platform for combat sports promoters (MMA, boxing, kickboxing, grappling). AI-powered event management with dynamic ticket pricing, real-time fight night dashboard, sponsor management, operational checklists, and revenue analytics.

## Architecture
- **Backend**: FastAPI + MongoDB (motor async) + JWT auth + bcrypt + OpenAI GPT via emergentintegrations + Stripe Checkout via emergentintegrations
- **Frontend**: React 19 + Tailwind CSS + Radix UI + Phosphor Icons + React Router + Recharts
- **Database**: MongoDB (collections: users, events, fighters, bouts, tasks, financials, sponsors, checklist_templates, payment_transactions, pricing_configs, login_attempts)
- **AI**: OpenAI GPT via Emergent LLM Key (promo generation, matchup suggestions, smart reminders, pricing recommendations)
- **Payments**: Stripe Checkout via Emergent with dynamic pricing (4 tiers: General $65, VIP $150, Ringside $350, PPV $29.99 - base prices)

## What's Been Implemented

### Phase 1 (2026-04-13) - MVP
- Auth (JWT + bcrypt), Events/Fighters/Bouts CRUD, Tasks, Financials, AI Promo/Matchups
- Neo-brutalist UFC-style UI, 6 seeded fighters, 3 seeded events

### Phase 2 (2026-04-13) - Expansion
- FightJudge Pro rebrand, Fight Night Live Dashboard, Sponsors Management
- Checklists (4 templates: Daily/Weekly/Monthly/Event Day), Revenue Analytics with charts
- Stripe Ticketing (4 packages), Smart AI Reminders

### Phase 3 (2026-04-13) - Dynamic Pricing
- **Dynamic Pricing Algorithm**: 3-factor pricing (scarcity/urgency/velocity) with 0.8x-2.5x bounds
  - Scarcity: Adjusts based on % capacity sold (0-50%: 1.0x → 90%+: 1.5x)
  - Urgency: Days to event (30+ days: 1.0x → event day: 1.4x)
  - Velocity: Sales per day over 7-day window (slow: 0.9x discount → hot: 1.25x)
- **Pricing Intelligence Dashboard**: Overview table with all factors, sales by package chart, daily sales trend
- **Sales Analytics**: Total sold, revenue, capacity utilization, per-package breakdown
- **AI Pricing Recommendations**: GPT analyzes event data and recommends optimal pricing strategies
- Dynamic pricing used at checkout (actual Stripe amount = dynamic price)

## Testing Status
- Phase 3: Backend 50/50 (100%), Frontend 100%, Integration 100%, Zero regressions

## Prioritized Backlog
### P1 (High)
- Google OAuth social login
- Mobile responsive sidebar
- Bout result recording with fighter record auto-update
- Custom checklist template creation UI
- Event detail page with linked bouts/tasks/financials

### P2 (Medium)
- Calendar view, CSV/PDF export, Email/SMS (Twilio), Fighter photos
- Social media scheduler, Fan engagement tools
- Dynamic pricing history/audit log
- Price alert notifications when surge triggers

### P3 (Low)
- Dark mode, Event poster AI generation, Weight class rankings
- Historical analytics, Live stream overlays
- Compliance AI (Texas TDLR filings), Crowd prediction AI
- Fight Judge CV model integration endpoints
