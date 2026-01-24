import { createContext, useContext, useState, useEffect } from "react";
import api from "../lib/api";
import { useNavigate } from "react-router-dom";

const AuthContext = createContext(null);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const navigate = useNavigate();

  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const auth = localStorage.getItem("isAuthenticated") === "true";
    setIsAuthenticated(auth);
    setLoading(false);
  }, []);

  const login = async (password) => {
    const response = await api.post("/api/login", { password });

    if (response.data.success) {
      localStorage.setItem("isAuthenticated", "true");
      setIsAuthenticated(true);
      navigate("/");
    }

    return response.data;
  };

  const logout = () => {
    localStorage.removeItem("isAuthenticated");
    setIsAuthenticated(false);
    navigate("/login");
  };

  return (
    <AuthContext.Provider
      value={{ isAuthenticated, loading, login, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
};
