import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { CheckCircle, SpinnerGap, XCircle } from '@phosphor-icons/react';

export default function TicketSuccessPage() {
  const { api } = useAuth();
  const [searchParams] = useSearchParams();
  const [status, setStatus] = useState('checking');
  const [attempts, setAttempts] = useState(0);

  const sessionId = searchParams.get('session_id');

  useEffect(() => {
    if (!sessionId) { setStatus('error'); return; }

    const pollStatus = async () => {
      try {
        const { data } = await api.get(`/tickets/status/${sessionId}`);
        if (data.payment_status === 'paid') {
          setStatus('success');
          return;
        }
        if (data.status === 'expired') {
          setStatus('expired');
          return;
        }
        if (attempts < 5) {
          setTimeout(() => setAttempts(a => a + 1), 2000);
        } else {
          setStatus('timeout');
        }
      } catch {
        setStatus('error');
      }
    };

    pollStatus();
  }, [sessionId, attempts, api]);

  return (
    <div data-testid="ticket-success-page" className="animate-in max-w-lg mx-auto mt-16">
      <div className="card-brutal p-8 text-center">
        {status === 'checking' && (
          <>
            <SpinnerGap size={48} weight="bold" className="mx-auto mb-4 text-[#D4AF37] animate-spin" />
            <h2 className="font-heading text-3xl uppercase mb-2">Processing Payment</h2>
            <p className="text-zinc-500">Verifying your payment status...</p>
          </>
        )}
        {status === 'success' && (
          <>
            <CheckCircle size={48} weight="fill" className="mx-auto mb-4 text-green-600" />
            <h2 className="font-heading text-3xl uppercase mb-2 text-green-600">Payment Successful!</h2>
            <p className="text-zinc-500 mb-6">Your ticket has been confirmed. Check your purchase history for details.</p>
            <a href="/tickets" className="btn-accent inline-block">Back to Ticketing</a>
          </>
        )}
        {(status === 'error' || status === 'expired' || status === 'timeout') && (
          <>
            <XCircle size={48} weight="fill" className="mx-auto mb-4 text-red-600" />
            <h2 className="font-heading text-3xl uppercase mb-2 text-red-600">
              {status === 'expired' ? 'Session Expired' : 'Payment Issue'}
            </h2>
            <p className="text-zinc-500 mb-6">
              {status === 'expired' ? 'Your payment session has expired. Please try again.' : 'Unable to verify payment. Please check your purchase history or try again.'}
            </p>
            <a href="/tickets" className="btn-primary inline-block">Try Again</a>
          </>
        )}
      </div>
    </div>
  );
}
