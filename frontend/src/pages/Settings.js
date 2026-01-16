import { useState, useEffect } from "react";
import { Link, useSearchParams } from "react-router-dom";
import api from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Badge } from "../components/ui/badge";
import { toast } from "sonner";
import { 
  ArrowLeft, Save, Link2, CheckCircle, AlertCircle,
  RefreshCw, ExternalLink
} from "lucide-react";

export default function Settings() {
  const [searchParams] = useSearchParams();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [fetchingPolicies, setFetchingPolicies] = useState(false);
  
  const [settings, setSettings] = useState({
    fulfillment_policy_id: "",
    return_policy_id: "",
    payment_policy_id: "",
    merchant_location_key: "",
    ebay_connected: false
  });
  
  const [policies, setPolicies] = useState(null);

  useEffect(() => {
    if (searchParams.get("ebay_connected") === "true") {
      toast.success("eBay account connected successfully!");
    }
    fetchSettings();
  }, [searchParams]);

  const fetchSettings = async () => {
    try {
      const response = await api.get("/settings");
      setSettings(response.data);
    } catch (error) {
      toast.error("Failed to load settings");
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.patch("/settings", {
        fulfillment_policy_id: settings.fulfillment_policy_id || null,
        return_policy_id: settings.return_policy_id || null,
        payment_policy_id: settings.payment_policy_id || null,
        merchant_location_key: settings.merchant_location_key || null
      });
      toast.success("Settings saved");
    } catch (error) {
      toast.error("Failed to save settings");
    } finally {
      setSaving(false);
    }
  };

  const handleConnectEbay = async () => {
    try {
      const response = await api.get("/ebay/auth/start");
      window.location.href = response.data.auth_url;
    } catch (error) {
      const detail = error.response?.data?.detail;
      toast.error(detail || "Failed to start eBay connection");
    }
  };

  const fetchPolicies = async () => {
    setFetchingPolicies(true);
    try {
      const response = await api.get("/ebay/policies");
      setPolicies(response.data);
      toast.success("Policies fetched from eBay");
    } catch (error) {
      toast.error("Failed to fetch policies. Make sure eBay is connected.");
    } finally {
      setFetchingPolicies(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="font-mono">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="bg-card border-b-2 border-border">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-4">
              <Link to="/" className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors">
                <ArrowLeft className="w-4 h-4" />
                <span className="font-bold text-sm uppercase tracking-wider">Back</span>
              </Link>
              <h1 className="font-heading font-bold text-xl uppercase tracking-tight">Settings</h1>
            </div>
            <Button
              onClick={handleSave}
              disabled={saving}
              className="bg-primary text-primary-foreground border-2 border-border shadow-hard hover:translate-y-[2px] hover:shadow-hard-sm transition-all uppercase font-bold tracking-wider text-sm"
              data-testid="save-settings-btn"
            >
              <Save className="w-4 h-4 mr-2" />
              {saving ? "Saving..." : "Save"}
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        {/* eBay Connection */}
        <div className="bg-card border-2 border-border p-6 shadow-hard">
          <h2 className="font-heading font-bold text-xl uppercase tracking-tight mb-4 border-b-2 border-border pb-2">
            eBay Connection
          </h2>
          
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {settings.ebay_connected ? (
                <>
                  <CheckCircle className="w-6 h-6 text-green-600" />
                  <div>
                    <p className="font-bold">Connected</p>
                    <p className="text-sm text-muted-foreground font-mono">eBay Sandbox account linked</p>
                  </div>
                </>
              ) : (
                <>
                  <AlertCircle className="w-6 h-6 text-amber-500" />
                  <div>
                    <p className="font-bold">Not Connected</p>
                    <p className="text-sm text-muted-foreground font-mono">Connect your eBay account to publish listings</p>
                  </div>
                </>
              )}
            </div>
            
            <Button
              variant={settings.ebay_connected ? "outline" : "default"}
              onClick={handleConnectEbay}
              className={`border-2 border-border shadow-hard hover:translate-y-[2px] hover:shadow-hard-sm transition-all uppercase font-bold tracking-wider text-sm ${
                settings.ebay_connected ? '' : 'bg-primary text-primary-foreground'
              }`}
              data-testid="connect-ebay-btn"
            >
              <Link2 className="w-4 h-4 mr-2" />
              {settings.ebay_connected ? "Reconnect" : "Connect eBay"}
            </Button>
          </div>
        </div>

        {/* Business Policies */}
        <div className="bg-card border-2 border-border p-6 shadow-hard">
          <div className="flex items-center justify-between mb-4 border-b-2 border-border pb-2">
            <h2 className="font-heading font-bold text-xl uppercase tracking-tight">
              Business Policies
            </h2>
            {settings.ebay_connected && (
              <Button
                variant="outline"
                size="sm"
                onClick={fetchPolicies}
                disabled={fetchingPolicies}
                className="border-2 border-border shadow-hard-sm hover:translate-y-[1px] hover:shadow-none transition-all uppercase font-bold text-xs tracking-wider"
                data-testid="fetch-policies-btn"
              >
                <RefreshCw className={`w-4 h-4 mr-2 ${fetchingPolicies ? 'animate-spin' : ''}`} />
                Fetch from eBay
              </Button>
            )}
          </div>
          
          <p className="text-muted-foreground font-mono text-sm mb-6">
            Enter your eBay business policy IDs. These are required to publish listings.
          </p>
          
          <div className="space-y-4">
            <div className="space-y-2">
              <Label className="text-xs font-bold uppercase tracking-widest">Fulfillment Policy ID</Label>
              <Input
                value={settings.fulfillment_policy_id || ""}
                onChange={(e) => setSettings(prev => ({ ...prev, fulfillment_policy_id: e.target.value }))}
                placeholder="e.g., 12345678901"
                className="border-2 border-border font-mono"
                data-testid="fulfillment-policy-input"
              />
              {policies?.fulfillment_policies?.length > 0 && (
                <div className="flex flex-wrap gap-2 mt-2">
                  {policies.fulfillment_policies.map(p => (
                    <Badge
                      key={p.fulfillmentPolicyId}
                      variant="outline"
                      className="cursor-pointer border-2 border-border hover:bg-muted"
                      onClick={() => setSettings(prev => ({ ...prev, fulfillment_policy_id: p.fulfillmentPolicyId }))}
                    >
                      {p.name}: {p.fulfillmentPolicyId}
                    </Badge>
                  ))}
                </div>
              )}
            </div>
            
            <div className="space-y-2">
              <Label className="text-xs font-bold uppercase tracking-widest">Return Policy ID</Label>
              <Input
                value={settings.return_policy_id || ""}
                onChange={(e) => setSettings(prev => ({ ...prev, return_policy_id: e.target.value }))}
                placeholder="e.g., 12345678902"
                className="border-2 border-border font-mono"
                data-testid="return-policy-input"
              />
              {policies?.return_policies?.length > 0 && (
                <div className="flex flex-wrap gap-2 mt-2">
                  {policies.return_policies.map(p => (
                    <Badge
                      key={p.returnPolicyId}
                      variant="outline"
                      className="cursor-pointer border-2 border-border hover:bg-muted"
                      onClick={() => setSettings(prev => ({ ...prev, return_policy_id: p.returnPolicyId }))}
                    >
                      {p.name}: {p.returnPolicyId}
                    </Badge>
                  ))}
                </div>
              )}
            </div>
            
            <div className="space-y-2">
              <Label className="text-xs font-bold uppercase tracking-widest">Payment Policy ID</Label>
              <Input
                value={settings.payment_policy_id || ""}
                onChange={(e) => setSettings(prev => ({ ...prev, payment_policy_id: e.target.value }))}
                placeholder="e.g., 12345678903"
                className="border-2 border-border font-mono"
                data-testid="payment-policy-input"
              />
              {policies?.payment_policies?.length > 0 && (
                <div className="flex flex-wrap gap-2 mt-2">
                  {policies.payment_policies.map(p => (
                    <Badge
                      key={p.paymentPolicyId}
                      variant="outline"
                      className="cursor-pointer border-2 border-border hover:bg-muted"
                      onClick={() => setSettings(prev => ({ ...prev, payment_policy_id: p.paymentPolicyId }))}
                    >
                      {p.name}: {p.paymentPolicyId}
                    </Badge>
                  ))}
                </div>
              )}
            </div>
            
            <div className="space-y-2">
              <Label className="text-xs font-bold uppercase tracking-widest">Merchant Location Key (Optional)</Label>
              <Input
                value={settings.merchant_location_key || ""}
                onChange={(e) => setSettings(prev => ({ ...prev, merchant_location_key: e.target.value }))}
                placeholder="e.g., WAREHOUSE_MILAN"
                className="border-2 border-border font-mono"
                data-testid="location-key-input"
              />
            </div>
          </div>
        </div>

        {/* Shipping Presets Info */}
        <div className="bg-card border-2 border-border p-6 shadow-hard">
          <h2 className="font-heading font-bold text-xl uppercase tracking-tight mb-4 border-b-2 border-border pb-2">
            Default Shipping Rates
          </h2>
          <p className="text-muted-foreground font-mono text-sm mb-4">
            These shipping rates are applied to all listings via your fulfillment policy:
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="bg-muted p-4 border-2 border-border">
              <p className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Europe</p>
              <p className="font-mono text-lg mt-1">$10</p>
              <p className="text-xs text-muted-foreground font-mono">Incl. UK & Switzerland</p>
            </div>
            <div className="bg-muted p-4 border-2 border-border">
              <p className="text-xs font-bold uppercase tracking-widest text-muted-foreground">USA + Canada</p>
              <p className="font-mono text-lg mt-1">$25</p>
            </div>
            <div className="bg-muted p-4 border-2 border-border">
              <p className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Rest of World</p>
              <p className="font-mono text-lg mt-1">$45</p>
            </div>
          </div>
          <p className="text-muted-foreground font-mono text-xs mt-4">
            Handling time: 2 business days · Returns: 30 days, buyer pays return shipping
          </p>
        </div>

        {/* eBay Setup Instructions */}
        <div className="bg-amber-50 border-2 border-amber-400 p-6">
          <h3 className="font-heading font-bold text-lg uppercase tracking-tight mb-3">
            First Time Setup
          </h3>
          <ol className="list-decimal list-inside space-y-2 font-mono text-sm text-amber-900">
            <li>Create an eBay Developer account at <a href="https://developer.ebay.com" target="_blank" rel="noopener noreferrer" className="underline inline-flex items-center gap-1">developer.ebay.com <ExternalLink className="w-3 h-3" /></a></li>
            <li>Generate Sandbox credentials (App ID = Client ID, Cert ID = Client Secret)</li>
            <li>Set your Redirect URI to: <code className="bg-amber-200 px-1">{window.location.origin}/api/ebay/auth/callback</code></li>
            <li>Add credentials to backend .env: EBAY_CLIENT_ID, EBAY_CLIENT_SECRET, EBAY_REDIRECT_URI</li>
            <li>Create a Sandbox test seller account and set up business policies</li>
            <li>Click "Connect eBay" above and authorize the app</li>
            <li>Fetch or manually enter your policy IDs</li>
          </ol>
        </div>
      </main>
    </div>
  );
}
