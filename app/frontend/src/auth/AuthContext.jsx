import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { api, tokenStore } from "../api.js";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const loadUser = useCallback(async () => {
    if (!tokenStore.get()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
     const me = await api.me();
      console.log("CURRENT USER:", JSON.stringify(me, null, 2));
      setUser(me);
    } catch {
      tokenStore.set(null);
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadUser();
    const onUnauth = () => setUser(null);
    window.addEventListener("agrismart:unauthorized", onUnauth);
    return () => window.removeEventListener("agrismart:unauthorized", onUnauth);
  }, [loadUser]);

  // Returns the whole TokenResponse (not just .user) — callers need `is_new`
  // to decide whether to route to profile completion or straight to the app.
  const finish = (resp) => {
    tokenStore.set(resp.access_token);
    setUser(resp.user);
    return resp;
  };

  const value = {
    user,
    loading,
    requestOtp: (phone, mode) => api.requestOtp(phone, mode),
    verifyOtp: async (phone, otp) => finish(await api.verifyOtp(phone, otp)),
    continueAsGuest: async () => finish(await api.continueAsGuest()),
    completeProfile: async (payload) => {
      const updated = await api.completeProfile(payload);
      setUser(updated);
      return updated;
    },
    // Same user id as before, so nothing they scanned or saved as a guest
    // needs to move anywhere.
    linkPhone: async (phone, otp) => {
      const updated = await api.linkPhone(phone, otp);
      setUser(updated);
      return updated;
    },
    updateProfile: async (payload) => {
      const updated = await api.updateProfile(payload);
      setUser(updated);
      return updated;
    },
    logout: () => {
      tokenStore.set(null);
      setUser(null);
    },
    setUser,
  };
  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}

export const useAuth = () => useContext(AuthCtx);

export function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-muted">
        Loading…
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace state={{ from: location }} />;
  return children;
}
