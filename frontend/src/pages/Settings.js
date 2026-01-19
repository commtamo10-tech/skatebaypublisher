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
  RefreshCw, ExternalLink, Bug, Globe, Zap, Loader2
} from "lucide-react";

export default function Settings() {
  const [searchParams] = useSearchParams();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [fetchingPolicies, setFetchingPolicies] = useState(false);
  const [bootstrapping, setBootstrapping] = useState(false);
  const [debugInfo, setDebugInfo] = useState(null);
  const [showDebug, setShowDebug] = useState(false);
  const [marketplaces, setMarketplaces] = useState([]);
  const [bootstrapResults, setBootstrapResults] = useState(null);
  
  const [settings, setSettings] = useState({
    fulfillment_policy_id: "",
    return_policy_id: "",
    payment_policy_id: "",
    merchant_location_key: "",
    ebay_connected: false,
    ebay_environment: "sandbox"
  });
  
  const [policies, setPolicies] = useState(null);

  useEffect(() => {
    // Handle OAuth success
    if (searchParams.get("ebay_connected") === "true") {
      const env = searchParams.get("environment") || "sandbox";
      toast.success(`eBay ${env} account connected successfully!`);
      // Clear URL params
      window.history.replaceState({}, '', '/settings');
    }
    
    // Handle OAuth errors
    const ebayError = searchParams.get("ebay_error");
    const ebayErrorDesc = searchParams.get("ebay_error_desc");
    if (ebayError) {
      toast.error(`eBay connection failed: ${ebayErrorDesc || ebayError}`);
      console.error("eBay OAuth Error:", ebayError, ebayErrorDesc);
      // Clear URL params
      window.history.replaceState({}, '', '/settings');
    }
    
    fetchSettings();
    fetchMarketplaces();
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

  const fetchMarketplaces = async () => {
    try {
      const response = await api.get("/marketplaces");
      setMarketplaces(response.data.marketplaces || []);
    } catch (error) {
      console.error("Failed to fetch marketplaces:", error);
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
      // Open in new window to avoid potential iframe/security restrictions
      // Some browsers block redirects from certain contexts
      const authUrl = response.data.auth_url;
      console.log("Opening eBay OAuth URL:", authUrl);
      
      // Try opening in same window first
      window.location.href = authUrl;
    } catch (error) {
      const detail = error.response?.data?.detail;
      toast.error(detail || "Failed to start eBay connection");
    }
  };

  const fetchDebugInfo = async () => {
    try {
      const response = await api.get("/ebay/debug");
      setDebugInfo(response.data);
      setShowDebug(true);
      console.log("eBay Debug Info:", response.data);
    } catch (error) {
      console.error("Debug fetch error:", error);
      toast.error("Failed to fetch debug info");
    }
  };

  const fetchPolicies = async () => {
    setFetchingPolicies(true);
    try {
      const response = await api.get("/ebay/policies");
      const data = response.data;
      setPolicies(data);
      
      // Log response for debugging
      console.log("eBay Policies Response:", data);
      
      // Auto-fill the first available policy ID for each type
      const updates = {};
      
      if (data.fulfillment_policies?.length > 0) {
        const policyId = data.fulfillment_policies[0].fulfillmentPolicyId;
        if (policyId && !settings.fulfillment_policy_id) {
          updates.fulfillment_policy_id = policyId;
        }
      }
      
      if (data.return_policies?.length > 0) {
        const policyId = data.return_policies[0].returnPolicyId;
        if (policyId && !settings.return_policy_id) {
          updates.return_policy_id = policyId;
        }
      }
      
      if (data.payment_policies?.length > 0) {
        const policyId = data.payment_policies[0].paymentPolicyId;
        if (policyId && !settings.payment_policy_id) {
          updates.payment_policy_id = policyId;
        }
      }
      
      // Also check for newly created policies
      if (data.created_policies) {
        if (data.created_policies.fulfillment) {
          updates.fulfillment_policy_id = data.created_policies.fulfillment;
        }
        if (data.created_policies.return) {
          updates.return_policy_id = data.created_policies.return;
        }
        if (data.created_policies.payment) {
          updates.payment_policy_id = data.created_policies.payment;
        }
      }
      
      if (Object.keys(updates).length > 0) {
        setSettings(prev => ({ ...prev, ...updates }));
        toast.success(`Policies fetched and ${Object.keys(updates).length} field(s) auto-filled!`);
      } else if (data.fulfillment_policies?.length === 0 && data.payment_policies?.length === 0 && data.return_policies?.length === 0) {
        toast.warning("No policies found on eBay. Default policies could not be created.");
      } else {
        toast.success("Policies fetched from eBay");
      }
    } catch (error) {
      console.error("Fetch policies error:", error);
      const detail = error.response?.data?.detail;
      if (detail?.includes("not connected")) {
        toast.error("eBay not connected. Please click 'Connect eBay' first and complete authorization.");
      } else {
        toast.error(detail || "Failed to fetch policies. Check console for details.");
      }
    } finally {
      setFetchingPolicies(false);
    }
  };

  const handleBootstrapMarketplaces = async () => {
    if (!settings.ebay_connected) {
      toast.error("Please connect your eBay account first");
      return;
    }
    
    setBootstrapping(true);
    setBootstrapResults(null);
    
    try {
      toast.info("Starting multi-marketplace bootstrap... This may take a minute.");
      
      const response = await api.post("/settings/ebay/bootstrap-marketplaces");
      const data = response.data;
      
      console.log("Bootstrap Results:", data);
      setBootstrapResults(data);
      
      // Refresh marketplaces
      await fetchMarketplaces();
      
      const { success, partial, failed } = data.summary;
      if (success > 0 && failed === 0) {
        toast.success(`Bootstrap complete! ${success} marketplace(s) configured.`);
      } else if (success > 0) {
        toast.warning(`Bootstrap partial: ${success} OK, ${partial} partial, ${failed} failed`);
      } else {
        toast.error(`Bootstrap failed for all marketplaces. Check logs.`);
      }
    } catch (error) {
      console.error("Bootstrap error:", error);
      const detail = error.response?.data?.detail;
      toast.error(detail || "Bootstrap failed. Check console for details.");
    } finally {
      setBootstrapping(false);
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
        {/* Environment Toggle */}
        <div className="bg-card border-2 border-border p-6 shadow-hard">
          <h2 className="font-heading font-bold text-xl uppercase tracking-tight mb-4 border-b-2 border-border pb-2">
            <Globe className="w-5 h-5 inline mr-2" />
            eBay Environment
          </h2>
          
          <div className="flex items-center gap-4">
            <button
              onClick={() => setSettings({...settings, ebay_environment: "sandbox", ebay_connected: false})}
              className={`px-6 py-3 font-bold uppercase tracking-wider text-sm border-2 transition-all ${
                settings.ebay_environment === "sandbox"
                  ? "bg-amber-500 text-white border-amber-600 shadow-hard"
                  : "bg-muted text-muted-foreground border-border hover:bg-muted/80"
              }`}
              data-testid="env-sandbox-btn"
            >
              🧪 Sandbox
            </button>
            <button
              onClick={() => setSettings({...settings, ebay_environment: "production", ebay_connected: false})}
              className={`px-6 py-3 font-bold uppercase tracking-wider text-sm border-2 transition-all ${
                settings.ebay_environment === "production"
                  ? "bg-green-600 text-white border-green-700 shadow-hard"
                  : "bg-muted text-muted-foreground border-border hover:bg-muted/80"
              }`}
              data-testid="env-production-btn"
            >
              🚀 Production (ebay.it)
            </button>
          </div>
          
          <p className="mt-3 text-sm text-muted-foreground font-mono">
            {settings.ebay_environment === "production" 
              ? "⚠️ Production mode: Listings will be published to your real eBay.it shop"
              : "Sandbox mode: Test listings on eBay Sandbox (not visible to buyers)"
            }
          </p>
          
          {settings.ebay_environment === "production" && (
            <div className="mt-3 p-3 bg-amber-50 border-2 border-amber-300 text-amber-800 text-sm font-mono">
              <strong>Important:</strong> Make sure you have configured EBAY_PROD_CLIENT_ID, EBAY_PROD_CLIENT_SECRET, and EBAY_PROD_RUNAME in environment variables.
            </div>
          )}
        </div>

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
                    <p className="text-sm text-muted-foreground font-mono">
                      eBay {settings.ebay_environment === "production" ? "Production (ebay.it)" : "Sandbox"} account linked
                    </p>
                  </div>
                </>
              ) : (
                <>
                  <AlertCircle className="w-6 h-6 text-amber-500" />
                  <div>
                    <p className="font-bold">Not Connected</p>
                    <p className="text-sm text-muted-foreground font-mono">
                      Connect your eBay {settings.ebay_environment === "production" ? "Production" : "Sandbox"} account to publish listings
                    </p>
                  </div>
                </>
              )}
            </div>
            
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={fetchDebugInfo}
                className="border-2 border-border shadow-hard-sm hover:translate-y-[1px] hover:shadow-none transition-all uppercase font-bold text-xs tracking-wider"
                data-testid="debug-ebay-btn"
              >
                <Bug className="w-4 h-4 mr-1" />
                Debug
              </Button>
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
          
          {/* Debug Info Panel */}
          {showDebug && debugInfo && (
            <div className="mt-4 p-4 bg-muted border-2 border-border font-mono text-sm">
              <div className="flex items-center justify-between mb-2">
                <span className="font-bold uppercase text-xs tracking-wider">Debug Info</span>
                <button 
                  onClick={() => setShowDebug(false)}
                  className="text-muted-foreground hover:text-foreground"
                >
                  ✕
                </button>
              </div>
              <div className="space-y-1">
                <p><span className="text-muted-foreground">environment:</span> <span className="font-bold">{debugInfo.environment || 'sandbox'}</span></p>
                <p><span className="text-muted-foreground">connected:</span> <span className={debugInfo.connected ? 'text-green-600' : 'text-red-600'}>{String(debugInfo.connected)}</span></p>
                <p><span className="text-muted-foreground">has_access_token:</span> <span className={debugInfo.has_access_token ? 'text-green-600' : 'text-red-600'}>{String(debugInfo.has_access_token)}</span></p>
                <p><span className="text-muted-foreground">has_refresh_token:</span> <span className={debugInfo.has_refresh_token ? 'text-green-600' : 'text-red-600'}>{String(debugInfo.has_refresh_token)}</span></p>
                <p><span className="text-muted-foreground">token_expires_at:</span> {debugInfo.token_expires_at || 'null'}</p>
                <p><span className="text-muted-foreground">is_expired:</span> {String(debugInfo.is_expired)}</p>
                <p><span className="text-muted-foreground">scopes:</span> {debugInfo.scopes?.join(', ') || 'none'}</p>
                <p><span className="text-muted-foreground">updated_at:</span> {debugInfo.updated_at || 'null'}</p>
                <p className="pt-2 text-muted-foreground italic">{debugInfo.message}</p>
              </div>
            </div>
          )}
        </div>

        {/* Multi-Marketplace Configuration */}
        <div className="bg-card border-2 border-border p-6 shadow-hard">
          <div className="flex items-center justify-between mb-4 border-b-2 border-border pb-2">
            <h2 className="font-heading font-bold text-xl uppercase tracking-tight">
              <Globe className="w-5 h-5 inline mr-2" />
              Multi-Marketplace
            </h2>
            <Button
              onClick={handleBootstrapMarketplaces}
              disabled={bootstrapping || !settings.ebay_connected}
              className="bg-gradient-to-r from-blue-600 to-purple-600 text-white border-2 border-blue-700 shadow-hard hover:translate-y-[2px] hover:shadow-hard-sm transition-all uppercase font-bold tracking-wider text-sm"
              data-testid="bootstrap-marketplaces-btn"
            >
              {bootstrapping ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Bootstrapping...
                </>
              ) : (
                <>
                  <Zap className="w-4 h-4 mr-2" />
                  Bootstrap Marketplaces
                </>
              )}
            </Button>
          </div>
          
          <p className="text-muted-foreground font-mono text-sm mb-4">
            Auto-configure policies and locations for all supported marketplaces (US, DE, ES, AU).
            <br />
            <span className="text-xs">
              Creates: inventory location, fulfillment policy, payment policy, return policy (30 days, seller pays, domestic only).
            </span>
          </p>
          
          {/* Bootstrap Results */}
          {bootstrapResults && (
            <div className="mb-4 p-4 bg-muted border-2 border-border">
              <h3 className="font-bold text-sm uppercase tracking-wider mb-2">Bootstrap Results</h3>
              <div className="space-y-2">
                {bootstrapResults.results?.map((r, i) => (
                  <div key={i} className={`p-2 border ${r.success ? 'border-green-500 bg-green-50' : 'border-amber-500 bg-amber-50'}`}>
                    <div className="flex items-center gap-2">
                      {r.success ? (
                        <CheckCircle className="w-4 h-4 text-green-600" />
                      ) : (
                        <AlertCircle className="w-4 h-4 text-amber-600" />
                      )}
                      <span className="font-bold font-mono">{r.marketplace_id}</span>
                    </div>
                    {r.error && <p className="text-sm text-red-600 mt-1">{r.error}</p>}
                    {r.success && (
                      <div className="text-xs font-mono mt-1 text-muted-foreground">
                        Location: {r.location_key} | Shipping: {r.shipping_service_code}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
          
          {/* Marketplace Status Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {marketplaces.map((mp) => (
              <div 
                key={mp.id}
                className={`p-4 border-2 ${mp.is_configured ? 'border-green-500 bg-green-50' : 'border-border bg-muted'}`}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="font-bold">{mp.name}</span>
                  <Badge variant={mp.is_configured ? "default" : "outline"} className={mp.is_configured ? 'bg-green-600' : ''}>
                    {mp.is_configured ? "Ready" : "Not Configured"}
                  </Badge>
                </div>
                <div className="text-xs font-mono space-y-1 text-muted-foreground">
                  <p>Currency: {mp.currency}</p>
                  <p>Default Price: {mp.default_price} {mp.currency}</p>
                  <p>Shipping: {mp.default_shipping} {mp.currency}</p>
                  {mp.merchant_location_key && (
                    <p className="text-green-700">Location: {mp.merchant_location_key}</p>
                  )}
                  {mp.policies?.fulfillment_policy_id && (
                    <p className="text-green-700 truncate" title={mp.policies.fulfillment_policy_id}>
                      Fulfillment: {mp.policies.fulfillment_policy_id.slice(0, 12)}...
                    </p>
                  )}
                </div>
              </div>
            ))}
            
            {marketplaces.length === 0 && (
              <div className="col-span-2 text-center py-4 text-muted-foreground font-mono">
                No marketplace data. Click "Bootstrap Marketplaces" to configure.
              </div>
            )}
          </div>
        </div>

        {/* Business Policies (Legacy - single marketplace) */}
        <div className="bg-card border-2 border-border p-6 shadow-hard">
          <div className="flex items-center justify-between mb-4 border-b-2 border-border pb-2">
            <h2 className="font-heading font-bold text-xl uppercase tracking-tight">
              Legacy Policies (Single Marketplace)
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
            These are global policy IDs (used for single-marketplace publishing). For multi-marketplace, use the Bootstrap above.
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
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
            <div className="bg-muted p-4 border-2 border-border">
              <p className="text-xs font-bold uppercase tracking-widest text-muted-foreground">US</p>
              <p className="font-mono text-lg mt-1">$25 USD</p>
            </div>
            <div className="bg-muted p-4 border-2 border-border">
              <p className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Germany</p>
              <p className="font-mono text-lg mt-1">€12 EUR</p>
            </div>
            <div className="bg-muted p-4 border-2 border-border">
              <p className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Spain</p>
              <p className="font-mono text-lg mt-1">€12 EUR</p>
            </div>
            <div className="bg-muted p-4 border-2 border-border">
              <p className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Australia</p>
              <p className="font-mono text-lg mt-1">$100 AUD</p>
            </div>
          </div>
          <p className="text-muted-foreground font-mono text-xs mt-4">
            Handling time: {3} business days · Returns: 30 days, seller pays return shipping
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
            <li><strong>NEW:</strong> Click "Bootstrap Marketplaces" to auto-configure US, DE, ES, AU</li>
          </ol>
        </div>
      </main>
    </div>
  );
}
