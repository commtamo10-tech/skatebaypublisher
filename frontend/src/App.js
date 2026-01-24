import { BrowserRouter, Routes, Route } from "react-router-dom";
import { useAuth } from "./context/AuthContext";
import Login from "./pages/Login";
import Home from "./pages/Home";
import NewDraft from "./pages/NewDraft";

function Header() {
  const { logout, isAuthenticated } = useAuth();

  if (!isAuthenticated) return null;

  return (
    <header className="flex items-center justify-between px-6 py-4 border-b bg-white">
      <div className="font-bold">SKATEBAY</div>
      <button
        onClick={logout}
        className="bg-black text-white px-4 py-2"
      >
        LOGOUT
      </button>
    </header>
  );
}

export default function App() {
  const { isAuthenticated, loading } = useAuth();

  if (loading) return null;

  return (
    <BrowserRouter>
      <Header />
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/"
          element={isAuthenticated ? <Home /> : <Login />}
        />
        <Route
          path="/new"
          element={isAuthenticated ? <NewDraft /> : <Login />}
        />
      </Routes>
    </BrowserRouter>
  );
}
