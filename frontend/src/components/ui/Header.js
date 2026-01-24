import { useAuth } from "../../context/AuthContext";

export default function Header() {
  const { logout } = useAuth();

  return (
    <header
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        padding: "16px 32px",
        borderBottom: "2px solid black",
        background: "white",
      }}
    >
      <strong style={{ fontSize: 20 }}>🚚 SKATEBAY</strong>

      <button
        onClick={logout}
        style={{
          background: "#ff3b3b",
          color: "white",
          border: "none",
          padding: "10px 16px",
          cursor: "pointer",
          fontWeight: "bold",
        }}
      >
        LOGOUT
      </button>
    </header>
  );
}
