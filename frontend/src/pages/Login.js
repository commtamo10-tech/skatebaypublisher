import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { toast } from "sonner";
import { Lock, Truck } from "lucide-react";

export default function Login() {
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      const res = await fetch(
        `${process.env.REACT_APP_BACKEND_URL}/api/login`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ password }),
        }
      );

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || "Invalid password");
      }

      toast.success("Welcome back!");
      navigate("/");
    } catch (err) {
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background flex">
      {/* Left Panel */}
      <div className="hidden lg:flex lg:w-1/2 bg-foreground text-background p-12 flex-col justify-between">
        <div>
          <div className="flex items-center gap-3 mb-8">
            <Truck className="w-10 h-10" />
            <span className="font-heading font-black text-2xl uppercase">
              SkateBay
            </span>
          </div>

          <h1 className="font-heading font-black text-5xl uppercase leading-tight mb-6">
            Vintage<br />Skateboard<br />Listings
          </h1>

          <p className="text-lg opacity-80 font-mono">
            Semi-automatic eBay listing creation for your vintage skate shop.
          </p>
        </div>

        <div className="font-mono text-xs opacity-50">
          © 2025 Old School Skate Shop
        </div>
      </div>

      {/* Right Panel */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-md">
          <div className="lg:hidden flex items-center gap-3 mb-8">
            <Truck className="w-8 h-8" />
            <span className="font-heading font-black text-xl uppercase">
              SkateBay
            </span>
          </div>

          <div className="bg-card border-2 border-border p-8 shadow-hard">
            <div className="flex items-center gap-3 mb-6">
              <Lock className="w-6 h-6" />
              <h2 className="font-heading font-bold text-2xl uppercase">
                Admin Login
              </h2>
            </div>

            <form onSubmit={handleSubmit} className="space-y-6">
              <div className="space-y-2">
                <Label
                  htmlFor="password"
                  className="text-xs font-bold uppercase"
                >
                  Password
                </Label>

                <Input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter admin password"
                  required
                />
              </div>

              <Button
                type="submit"
                disabled={loading}
                className="w-full uppercase font-bold"
              >
                {loading ? "Signing in..." : "Sign In"}
              </Button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
