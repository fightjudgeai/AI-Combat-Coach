import React from "react";
import "@/App.css";
import "@/index.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./contexts/AuthContext";
import ProtectedRoute from "./components/ProtectedRoute";
import Layout from "./components/Layout";
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

const P = ({ children }) => <ProtectedRoute><Layout>{children}</Layout></ProtectedRoute>;

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
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
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
