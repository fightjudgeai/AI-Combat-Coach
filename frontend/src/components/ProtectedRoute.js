import React from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Navigate } from 'react-router-dom';

export default function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-white">
        <div className="text-center">
          <div className="w-12 h-12 bg-[#DC2626] mx-auto mb-4 animate-pulse" />
          <p className="font-heading text-2xl uppercase">Loading...</p>
        </div>
      </div>
    );
  }
  
  if (!user) return <Navigate to="/login" />;
  return children;
}
