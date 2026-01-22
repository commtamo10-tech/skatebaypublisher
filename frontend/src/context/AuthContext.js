import { createContext, useContext, useState, useEffect } from "react";
import api from "../lib/api";

const AuthContext = createContext(null);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const [isAuthenticated, setIsAuthenticated] = useState(() => {
    return localStorage.getItem("isAuthenticated") === "true";
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // auth già nota → niente redirect prematuro
    setLoading(false);
  }, []);

  const login = async (password) => {
    const response = await api.post("/api/login", { password });

    if (response.data.success) {
      localStorage.setItem("isAuthenticated", "true");
      setIsAuthenticated(true);
    }

    return response.data;
  };

  const logout = () => {
    localStorage.removeItem("isAuthenticated");
    setIsAuthenticated(false);
  };

  return (
    <AuthContext.Provider
      value={{
        isAuthenticated,
        loading,
        login,
        logout
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};
