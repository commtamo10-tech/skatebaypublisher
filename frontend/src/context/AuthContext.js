import { createContext, useContext, useEffect, useState } from "react";

const AuthContext = createContext(null);

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
};

export const AuthProvider = ({ children }) => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const auth = localStorage.getItem("isAuthenticated") === "true";
    setIsAuthenticated(auth);
    setLoading(false);
  }, []);

  // 🔥 LOGIN MOCK — SEMPRE OK
  const login = async () => {
    localStorage.setItem("isAuthenticated", "true");
    setIsAuthenticated(true);
    return { success: true };
  };

  const logout = () => {
    localStorage.removeItem("isAuthenticated");
    setIsAuthenticated(false);
    window.location.href = "/login";
  };

  return (
    <AuthContext.Provider
      value={{ isAuthenticated, loading, login, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
};
