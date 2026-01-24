import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function Login() {
  const navigate = useNavigate();
  const { login } = useAuth();

  const handleSubmit = async (e) => {
    e.preventDefault();
    await login(); // 🔥 LOGIN MOCK
    navigate("/");
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
          className="w-full mb-4 p-2 border"
        />

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
