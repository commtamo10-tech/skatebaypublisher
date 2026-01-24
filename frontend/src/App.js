import { BrowserRouter, Routes, Route } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import NewDraft from "./pages/NewDraft";
import DraftEditor from "./pages/DraftEditor";
import Login from "./pages/Login";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<Dashboard />} />
        <Route path="/new" element={<NewDraft />} />
        <Route path="/draft/:id" element={<DraftEditor />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
