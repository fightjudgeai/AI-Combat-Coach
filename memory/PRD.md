# FightPromo - Combat Sports Promoter SaaS

## Problem Statement
SaaS platform for combat sports promoters to manage daily, weekly, monthly operations around events. Modules: Event Management, Fighter Roster, Fight Card Builder, Task Management, Financial Tracking. AI tools for promo generation and matchup suggestions. Multi-role: Admin, Staff, Matchmaker. JWT auth. Design: Neo-brutalist UFC style, light theme.

## Architecture
- **Backend**: FastAPI + MongoDB (motor async) + JWT auth + bcrypt + OpenAI via emergentintegrations
- **Frontend**: React 19 + Tailwind CSS + Radix UI + Phosphor Icons + React Router
- **Database**: MongoDB (collections: users, events, fighters, bouts, tasks, financials, login_attempts)
- **AI**: OpenAI GPT via Emergent LLM Key for promo generation and matchup suggestions

## User Personas
- **Admin Promoter**: Full access to all modules, user management
- **Staff**: Event management, tasks, financials
- **Matchmaker**: Fighter roster, fight card builder, matchup suggestions

## Core Requirements
- [x] JWT Authentication (login/register/logout/refresh)
- [x] Role-based access (admin, staff, matchmaker)
- [x] Event Management CRUD
- [x] Fighter Roster CRUD with weight class filtering
- [x] Fight Card Builder with bout matchups
- [x] Task Management with priority, recurrence, event linkage
- [x] Financial Tracking (revenue/expense with event linkage)
- [x] AI Promo Description Generator
- [x] AI Fight Matchup Suggestions
- [x] Dashboard overview with key stats
- [x] Sample seed data (3 events, 6 fighters, admin user)

## What's Been Implemented (2026-04-13)
- Full backend with 25+ API endpoints
- Complete frontend with 9 pages and layout system
- Neo-brutalist UI with Bebas Neue typography, sharp edges, hard shadows
- Split-screen auth with dramatic fighter imagery
- All CRUD operations tested and working
- AI tools page with promo generator and matchup suggestion forms

## Testing Status
- Backend: 31/31 tests passed (100%)
- Frontend: All core features working (95%+)
- Integration: 100% frontend-backend communication

## Prioritized Backlog
### P0 (Critical)
- None remaining

### P1 (High)
- Google OAuth social login integration
- User management panel for admins
- Event detail page with linked bouts/tasks/financials
- Mobile responsive sidebar (hamburger menu)

### P2 (Medium)
- Bout result recording and fighter record auto-update
- Calendar view for events and tasks
- Export financials to CSV/PDF
- Email notifications for task deadlines
- Fighter profile pages with photo upload

### P3 (Low)
- Dark mode toggle
- Event poster/flyer generation with AI
- Weight class rankings
- Historical analytics dashboard
- Ticket sales integration
