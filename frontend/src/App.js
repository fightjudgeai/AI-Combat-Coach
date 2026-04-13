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

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/dashboard" element={<ProtectedRoute><Layout><DashboardPage /></Layout></ProtectedRoute>} />
          <Route path="/events" element={<ProtectedRoute><Layout><EventsPage /></Layout></ProtectedRoute>} />
          <Route path="/fighters" element={<ProtectedRoute><Layout><FightersPage /></Layout></ProtectedRoute>} />
          <Route path="/fight-cards" element={<ProtectedRoute><Layout><FightCardPage /></Layout></ProtectedRoute>} />
          <Route path="/tasks" element={<ProtectedRoute><Layout><TasksPage /></Layout></ProtectedRoute>} />
          <Route path="/finance" element={<ProtectedRoute><Layout><FinancePage /></Layout></ProtectedRoute>} />
          <Route path="/ai-tools" element={<ProtectedRoute><Layout><AIToolsPage /></Layout></ProtectedRoute>} />
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
