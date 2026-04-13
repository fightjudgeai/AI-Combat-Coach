# FightJudge Pro - Combat Sports Promoter SaaS

## Problem Statement
Revolutionary all-in-one SaaS for combat sports promoters. Manages every aspect of running a promotion: events, fighters, officials, venues, compliance, ticketing, finances, marketing, documents, and communications — all powered by AI.

## Architecture
- **Backend**: FastAPI + MongoDB (motor) + JWT + bcrypt + OpenAI GPT (emergentintegrations) + Stripe (emergentintegrations)
- **Frontend**: React 19 + Tailwind + Phosphor Icons + Recharts + React Router
- **DB Collections**: users, events, fighters, bouts, tasks, financials, sponsors, checklist_templates, payment_transactions, pricing_configs, officials, venues, fighter_medicals, fighter_contracts, licenses, medical_suspensions, messages, documents, campaigns, login_attempts
- **AI**: Promo generation, matchup suggestions, smart reminders, pricing recommendations, document generation, marketing content generation

## Implemented Modules (4 Phases)

### Phase 1 - MVP: Auth, Events, Fighters, Fight Cards, Tasks, Financials, AI Tools
### Phase 2 - Expansion: Fight Night Live, Sponsors, Checklists, Revenue Analytics, Stripe Ticketing, Smart Reminders
### Phase 3 - Dynamic Pricing: 3-factor pricing algorithm, pricing intelligence dashboard, AI recommendations
### Phase 4 - Enterprise (2026-04-13):
- **Officials & Staff**: Referee/judge/announcer/physician/cutman database with ratings, licenses, role filtering (5 seeded)
- **Venue Management**: Venue database with specs, capacity, rental cost, contacts, availability (3 seeded)
- **Compliance Engine**: License tracker with expiry alerts, medical suspensions with clear workflow, compliance dashboard (expired/expiring/active stats), unsigned contract tracking
- **Communication Hub**: Internal messaging (user-to-user + broadcast), priority levels, read/unread tracking
- **Document Management**: Manual creation + AI-powered document generation (bout agreements, venue contracts, medical forms, waivers, commission filings)
- **Marketing Engine**: Campaign management (email/SMS/social), AI content generation per campaign, audience targeting, status pipeline, campaign stats dashboard
- **Collapsible Sidebar**: Organized into 6 sections (Overview, Events, People, Operations, Business, Tools)
- **Public API**: No-auth public event pages with fight card data

## Testing: Phase 4 - Backend 34/34 (100%), Frontend 98%, Zero regressions

## Backlog
### P1: Google OAuth, mobile responsive, bout result recording, fighter portal, calendar view
### P2: Email/SMS integration (Twilio), fighter photos, e-signatures, social scheduler, seating chart builder
### P3: Dark mode, event poster AI, weight rankings, live stream overlays, attendance prediction, fan portal
