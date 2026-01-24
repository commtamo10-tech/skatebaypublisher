import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function Login() {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    const result = await login(password);

    if (result?.success) {
      navigate("/");
    } else {
      setError("Login failed");
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center">
      <form
        onSubmit={handleSubmit}
        className="bg-white p-6 border-2 border-black w-80"
      >
        <h2 className="text-xl font-bold mb-4">ADMIN LOGIN</h2>

        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full mb-4 p-2 border"
        />

        {error && (
          <div className="mb-3 text-red-600 text-sm">{error}</div>
        )}

        <button
          type="submit"
          className="w-full bg-red-500 text-white py-2"
        >
          Login
        </button>
      </form>
    </div>
  );
}
