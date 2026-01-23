import { Routes, Route, Navigate } from "react-router-dom";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import NewDraft from "./pages/NewDraft";
import NewBatch from "./pages/NewBatch";
import BatchReview from "./pages/BatchReview";
import DraftEditor from "./pages/DraftEditor";
import DraftPreview from "./pages/DraftPreview";
import Settings from "./pages/Settings";
import { Toaster } from "./components/ui/sonner";
import { useAuth } from "./context/AuthContext";

const ProtectedRoute = ({ children }) => {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return <div className="min-h-screen bg-background" />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return children;
};

export default function App() {
  return (
    <>
      <Routes>
        <Route path="/login" element={<Login />} />

        <Route path="/" element={
          <ProtectedRoute>
            <Dashboard />
          </ProtectedRoute>
        } />

        <Route path="/new" element={
          <ProtectedRoute>
            <NewDraft />
          </ProtectedRoute>
        } />

        <Route path="/batch/new" element={
          <ProtectedRoute>
            <NewBatch />
          </ProtectedRoute>
        } />

        <Route path="/batch/:batchId" element={
          <ProtectedRoute>
            <BatchReview />
          </ProtectedRoute>
        } />

        <Route path="/draft/:id" element={
          <ProtectedRoute>
            <DraftEditor />
          </ProtectedRoute>
        } />

        <Route path="/draft/:id/preview" element={
          <ProtectedRoute>
            <DraftPreview />
          </ProtectedRoute>
        } />

        <Route path="/settings" element={
          <ProtectedRoute>
            <Settings />
          </ProtectedRoute>
        } />

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>

      <Toaster position="top-right" />
    </>
  );
}
