import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { toast } from "sonner";
import { Lock, Truck } from "lucide-react";

export default function Login() {
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    
    try {
      await login(password);
      toast.success("Welcome back!");
      navigate("/");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Invalid password");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background flex">
      {/* Left Panel - Branding */}
      <div className="hidden lg:flex lg:w-1/2 bg-foreground text-background p-12 flex-col justify-between">
        <div>
          <div className="flex items-center gap-3 mb-8">
            <Truck className="w-10 h-10" strokeWidth={2} />
            <span className="font-heading font-black text-2xl uppercase tracking-tight">SkateBay</span>
          </div>
          <h1 className="font-heading font-black text-5xl uppercase tracking-tight leading-tight mb-6">
            Vintage<br />Skateboard<br />Listings
          </h1>
          <p className="text-lg text-muted opacity-80 font-mono">
            Semi-automatic eBay listing creation for your vintage skate shop.
          </p>
        </div>
        <div className="font-mono text-xs opacity-50">
          © 2025 Old School Skate Shop
        </div>
      </div>

      {/* Right Panel - Login Form */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-md">
          <div className="lg:hidden flex items-center gap-3 mb-8">
            <Truck className="w-8 h-8" strokeWidth={2} />
            <span className="font-heading font-black text-xl uppercase tracking-tight">SkateBay</span>
          </div>
          
          <div className="bg-card border-2 border-border p-8 shadow-hard">
            <div className="flex items-center gap-3 mb-6">
              <Lock className="w-6 h-6" strokeWidth={2} />
              <h2 className="font-heading font-bold text-2xl uppercase tracking-tight">Admin Login</h2>
            </div>
            
            <form onSubmit={handleSubmit} className="space-y-6">
              <div className="space-y-2">
                <Label htmlFor="password" className="text-xs font-bold uppercase tracking-widest">
                  Password
                </Label>
                <Input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter admin password"
                  className="border-2 border-border bg-input font-mono focus:shadow-hard-primary focus:border-primary transition-all"
                  data-testid="login-password-input"
                  required
                />
              </div>
              
              <Button
                type="submit"
                disabled={loading}
                className="w-full bg-primary text-primary-foreground border-2 border-border shadow-hard hover:translate-y-[2px] hover:shadow-hard-sm active:translate-y-[4px] active:shadow-none transition-all uppercase font-bold tracking-wider"
                data-testid="login-submit-btn"
              >
                {loading ? "Signing in..." : "Sign In"}
              </Button>
            </form>
            
            <p className="mt-6 text-xs text-muted-foreground font-mono text-center">
              Default password: admin123
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
