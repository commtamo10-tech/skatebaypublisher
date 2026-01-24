import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import NewDraft from "./pages/NewDraft";
import DraftEditor from "./pages/DraftEditor";
import Login from "./pages/Login";
import { useAuth } from "./context/AuthContext";

function App() {
  const { isAuthenticated, loading } = useAuth();

  if (loading) return null;

  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/login"
          element={
            isAuthenticated ? <Navigate to="/" replace /> : <Login />
          }
        />

        <Route
          path="/"
          element={
            isAuthenticated ? <Dashboard /> : <Navigate to="/login" replace />
          }
        />

        <Route
          path="/new"
          element={
            isAuthenticated ? <NewDraft /> : <Navigate to="/login" replace />
          }
        />

        <Route
          path="/draft/:id"
          element={
            isAuthenticated ? <DraftEditor /> : <Navigate to="/login" replace />
          }
        />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
