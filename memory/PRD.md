# FightJudge Pro - Combat Sports Promoter SaaS

## Problem Statement
Revolutionary all-in-one SaaS for combat sports promoters — manages every aspect of running a promotion with AI-powered tools, dual-portal system (Promoter + Fighter), and enterprise-grade features.

## Architecture
- **Backend**: FastAPI + MongoDB (motor) + JWT + bcrypt + OpenAI GPT + Stripe Checkout (all via emergentintegrations)
- **Frontend**: React 19 + Tailwind + Phosphor Icons + Recharts + React Router
- **20+ DB Collections**: users, events, fighters, bouts, tasks, financials, sponsors, checklist_templates, payment_transactions, pricing_configs, officials, venues, fighter_medicals, fighter_contracts, licenses, medical_suspensions, messages, documents, campaigns, login_attempts
- **AI Features**: Promo generation, matchup suggestions, smart reminders, pricing recommendations, document generation, marketing content generation

## Implemented (5 Phases)

### Phase 1 - MVP
Auth (JWT/bcrypt), Events CRUD, Fighter Roster, Fight Cards, Tasks, Financials, AI Tools (promo + matchups)

### Phase 2 - Expansion
Fight Night Live Dashboard, Sponsors, Checklists (4 templates), Revenue Analytics (charts), Stripe Ticketing, Smart AI Reminders

### Phase 3 - Dynamic Pricing
3-factor algorithm (scarcity/urgency/velocity), pricing intelligence dashboard, AI pricing recommendations

### Phase 4 - Enterprise
Officials & Staff (5 roles), Venue Management, Compliance Engine (licenses + suspensions), Communication Hub, Document Management (AI generation), Marketing Engine (AI content), Collapsible Sidebar (6 sections), Public Events API

### Phase 5 - Fighter Portal
- **Dual-Portal System**: Admin/Staff see promoter dashboard, Fighters see dedicated dark-themed portal
- **Fighter Dashboard**: Personal stats (record, upcoming bouts, suspensions, earnings, unread messages)
- **My Bouts**: Upcoming and past fight history with event details
- **Medical Status**: Active suspensions with alerts, medical clearance history
- **Contracts**: View bout agreements with purse/win bonus details
- **Payments**: Earnings history with career total
- **My Profile**: Self-service profile editing (gym, contact, emergency info, bio)
- **Messages**: Direct communication with promoter
- **Fighter Registration**: Dedicated signup flow (POST /api/auth/register-fighter)
- **Role-Based Routing**: Automatic redirect based on user role

## Testing: All 5 phases passing — Backend 100%, Frontend 95%+

## Backlog
### P1: Google OAuth, mobile responsive, calendar view, bout result recording
### P2: Twilio SMS/email, fighter photos, e-signatures, social media scheduler, seating chart
### P3: Dark mode toggle, event poster AI, live stream overlays, fan-facing ticket portal, attendance prediction
