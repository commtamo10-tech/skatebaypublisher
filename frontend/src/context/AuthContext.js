import { createContext, useContext, useState, useEffect } from "react";

const AuthContext = createContext(null);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const auth = localStorage.getItem("isAuthenticated") === "true";
    setIsAuthenticated(auth);
    setLoading(false);
  }, []);

  const login = async (password) => {
    // password fissa TEMPORANEA
    if (password === "admin") {
      localStorage.setItem("isAuthenticated", "true");
      setIsAuthenticated(true);
      return { success: true };
    }

    return { success: false };
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
