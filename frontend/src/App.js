import React from "react";
import "@/App.css";
import "@/index.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./contexts/AuthContext";
import ProtectedRoute from "./components/ProtectedRoute";
import Layout from "./components/Layout";
import FighterPortalLayout from "./components/FighterPortalLayout";
import CoachPortalLayout from "./components/CoachPortalLayout";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import DashboardPage from "./pages/DashboardPage";
import EventsPage from "./pages/EventsPage";
import FightersPage from "./pages/FightersPage";
import FightCardPage from "./pages/FightCardPage";
import TasksPage from "./pages/TasksPage";
import FinancePage from "./pages/FinancePage";
import AIToolsPage from "./pages/AIToolsPage";
import SponsorsPage from "./pages/SponsorsPage";
import ChecklistsPage from "./pages/ChecklistsPage";
import FightNightLivePage from "./pages/FightNightLivePage";
import TicketingPage from "./pages/TicketingPage";
import TicketSuccessPage from "./pages/TicketSuccessPage";
import OfficialsPage from "./pages/OfficialsPage";
import VenuesPage from "./pages/VenuesPage";
import CompliancePage from "./pages/CompliancePage";
import MessagesPage from "./pages/MessagesPage";
import DocumentsPage from "./pages/DocumentsPage";
import MarketingPage from "./pages/MarketingPage";
import FighterDashboard from "./pages/FighterDashboard";
import FighterBouts from "./pages/FighterBouts";
import FighterMedicals from "./pages/FighterMedicals";
import FighterContracts from "./pages/FighterContracts";
import FighterPayments from "./pages/FighterPayments";
import FighterProfile from "./pages/FighterProfile";
import FighterMessages from "./pages/FighterMessages";
import CoachDashboard from "./pages/CoachDashboard";
import CoachFighters from "./pages/CoachFighters";
import CoachBouts from "./pages/CoachBouts";
import CoachMessages from "./pages/CoachMessages";

const P = ({ children }) => <ProtectedRoute><Layout>{children}</Layout></ProtectedRoute>;
const FP = ({ children }) => <ProtectedRoute><FighterPortalLayout>{children}</FighterPortalLayout></ProtectedRoute>;
const CP = ({ children }) => <ProtectedRoute><CoachPortalLayout>{children}</CoachPortalLayout></ProtectedRoute>;

function RoleRouter() {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (!user) return <Navigate to="/login" replace />;
  if (user.role === 'fighter') return <Navigate to="/fighter-portal" replace />;
  if (user.role === 'coach') return <Navigate to="/coach-portal" replace />;
  return <Navigate to="/dashboard" replace />;
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          {/* Admin/Staff Routes */}
          <Route path="/dashboard" element={<P><DashboardPage /></P>} />
          <Route path="/events" element={<P><EventsPage /></P>} />
          <Route path="/fighters" element={<P><FightersPage /></P>} />
          <Route path="/fight-cards" element={<P><FightCardPage /></P>} />
          <Route path="/tasks" element={<P><TasksPage /></P>} />
          <Route path="/finance" element={<P><FinancePage /></P>} />
          <Route path="/ai-tools" element={<P><AIToolsPage /></P>} />
          <Route path="/sponsors" element={<P><SponsorsPage /></P>} />
          <Route path="/checklists" element={<P><ChecklistsPage /></P>} />
          <Route path="/live" element={<P><FightNightLivePage /></P>} />
          <Route path="/tickets" element={<P><TicketingPage /></P>} />
          <Route path="/tickets/success" element={<P><TicketSuccessPage /></P>} />
          <Route path="/officials" element={<P><OfficialsPage /></P>} />
          <Route path="/venues" element={<P><VenuesPage /></P>} />
          <Route path="/compliance" element={<P><CompliancePage /></P>} />
          <Route path="/messages" element={<P><MessagesPage /></P>} />
          <Route path="/documents" element={<P><DocumentsPage /></P>} />
          <Route path="/marketing" element={<P><MarketingPage /></P>} />
          {/* Fighter Portal */}
          <Route path="/fighter-portal" element={<FP><FighterDashboard /></FP>} />
          <Route path="/fighter-portal/bouts" element={<FP><FighterBouts /></FP>} />
          <Route path="/fighter-portal/medicals" element={<FP><FighterMedicals /></FP>} />
          <Route path="/fighter-portal/contracts" element={<FP><FighterContracts /></FP>} />
          <Route path="/fighter-portal/payments" element={<FP><FighterPayments /></FP>} />
          <Route path="/fighter-portal/profile" element={<FP><FighterProfile /></FP>} />
          <Route path="/fighter-portal/messages" element={<FP><FighterMessages /></FP>} />
          {/* Coach Portal */}
          <Route path="/coach-portal" element={<CP><CoachDashboard /></CP>} />
          <Route path="/coach-portal/fighters" element={<CP><CoachFighters /></CP>} />
          <Route path="/coach-portal/bouts" element={<CP><CoachBouts /></CP>} />
          <Route path="/coach-portal/messages" element={<CP><CoachMessages /></CP>} />
          {/* Role-based redirect */}
          <Route path="/" element={<RoleRouter />} />
          <Route path="*" element={<RoleRouter />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
