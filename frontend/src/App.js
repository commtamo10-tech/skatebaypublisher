import { BrowserRouter, Routes, Route } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import NewDraft from "./pages/NewDraft";
import DraftEditor from "./pages/DraftEditor";
import { AuthProvider } from "./context/AuthContext";

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* 🔥 LOGIN ELIMINATA */}
          <Route path="/" element={<Dashboard />} />
          <Route path="/new" element={<NewDraft />} />
          <Route path="/draft/:id" element={<DraftEditor />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
