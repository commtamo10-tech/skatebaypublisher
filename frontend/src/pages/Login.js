import { useState } from "react";
import { useAuth } from "../context/AuthContext";

export default function Login() {
  const { login } = useAuth();
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    try {
      await login();
    } catch (err) {
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

        {error && <div className="mb-2 text-red-600">{error}</div>}

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
