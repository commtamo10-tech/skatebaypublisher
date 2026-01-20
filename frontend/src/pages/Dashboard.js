import { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import api from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
import { toast } from "sonner";
import { 
  Plus, Search, Settings, LogOut, Truck, 
  FileText, CheckCircle, AlertCircle, Clock,
  Circle, Trash2, Upload, ExternalLink
} from "lucide-react";

const ITEM_TYPES = {
  WHL: { label: "Wheels", icon: "🛞" },
  TRK: { label: "Trucks", icon: "🔧" },
  DCK: { label: "Decks", icon: "🛹" },
};

const STATUS_STYLES = {
  DRAFT: { bg: "bg-gray-200", text: "text-black", icon: Clock },
  READY: { bg: "bg-amber-400", text: "text-black", icon: Circle },
  PUBLISHED: { bg: "bg-green-500", text: "text-white", icon: CheckCircle },
  ERROR: { bg: "bg-red-500", text: "text-white", icon: AlertCircle },
};

export default function Dashboard() {
  const { logout } = useAuth();
  const navigate = useNavigate();
  const [drafts, setDrafts] = useState([]);
  const [stats, setStats] = useState({ DRAFT: 0, READY: 0, PUBLISHED: 0, ERROR: 0, total: 0 });
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");

  useEffect(() => {
    fetchData();
  }, [statusFilter, typeFilter, search]);

  const fetchData = async () => {
    try {
      const params = {};
      if (statusFilter !== "all") params.status = statusFilter;
      if (typeFilter !== "all") params.item_type = typeFilter;
      if (search) params.search = search;

      const [draftsRes, statsRes] = await Promise.all([
        api.get("/drafts", { params }),
        api.get("/stats")
      ]);
      
      setDrafts(draftsRes.data);
      setStats(statsRes.data);
    } catch (error) {
      toast.error("Failed to load drafts");
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id, e) => {
    try {
      await api.delete(`/drafts/${id}`);
      toast.success("Draft cancellato!");
      await fetchData();
    } catch (error) {
      console.error("Delete error:", error);
      toast.error("Errore: " + (error.response?.data?.detail || "Impossibile cancellare"));
    }
  };

  const handleDeleteMarketplace = async (draftId, marketplaceId, e) => {
    e.stopPropagation();
    const marketplaceNames = {
      'EBAY_US': 'eBay.com',
      'EBAY_DE': 'eBay.de', 
      'EBAY_ES': 'eBay.es',
      'EBAY_AU': 'eBay.com.au'
    };
    const mpName = marketplaceNames[marketplaceId] || marketplaceId;
    
    if (!window.confirm(`Vuoi cancellare l'annuncio da ${mpName}?`)) {
      return;
    }
    
    try {
      await api.delete(`/drafts/${draftId}/marketplace/${marketplaceId}`);
      toast.success(`Annuncio rimosso da ${mpName}`);
      await fetchData();
    } catch (error) {
      console.error("Delete marketplace error:", error);
      toast.error("Errore: " + (error.response?.data?.detail || "Impossibile cancellare"));
    }
  };

  const StatCard = ({ label, value, icon: Icon, color }) => (
    <div className="bg-card border-2 border-border p-4 shadow-hard">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-widest text-muted-foreground">{label}</p>
          <p className="text-3xl font-heading font-black mt-1">{value}</p>
        </div>
        <Icon className={`w-8 h-8 ${color}`} strokeWidth={2} />
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="bg-card border-b-2 border-border sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <Truck className="w-8 h-8" strokeWidth={2} />
              <span className="font-heading font-black text-xl uppercase tracking-tight">SkateBay</span>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => navigate("/settings")}
                className="uppercase font-bold text-xs tracking-wider"
                data-testid="settings-btn"
              >
                <Settings className="w-4 h-4 mr-2" />
                Settings
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={logout}
                className="uppercase font-bold text-xs tracking-wider"
                data-testid="logout-btn"
              >
                <LogOut className="w-4 h-4 mr-2" />
                Logout
              </Button>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <StatCard label="Total" value={stats.total} icon={FileText} color="text-foreground" />
          <StatCard label="Drafts" value={stats.DRAFT} icon={Clock} color="text-gray-500" />
          <StatCard label="Ready" value={stats.READY} icon={Circle} color="text-amber-500" />
          <StatCard label="Published" value={stats.PUBLISHED} icon={CheckCircle} color="text-green-500" />
        </div>

        {/* Actions Bar */}
        <div className="flex flex-col sm:flex-row gap-4 mb-6">
          <Button
            onClick={() => navigate("/new")}
            className="bg-primary text-primary-foreground border-2 border-border shadow-hard hover:translate-y-[2px] hover:shadow-hard-sm active:translate-y-[4px] active:shadow-none transition-all uppercase font-bold tracking-wider"
            data-testid="new-draft-btn"
          >
            <Plus className="w-4 h-4 mr-2" />
            New Draft
          </Button>
          <Button
            onClick={() => navigate("/batch/new")}
            variant="outline"
            className="border-2 border-border shadow-hard hover:translate-y-[2px] hover:shadow-hard-sm active:translate-y-[4px] active:shadow-none transition-all uppercase font-bold tracking-wider"
            data-testid="batch-upload-btn"
          >
            <Upload className="w-4 h-4 mr-2" />
            Batch Upload
          </Button>
          
          <div className="flex-1 flex gap-2">
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="Search SKU..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-10 border-2 border-border font-mono"
                data-testid="search-input"
              />
            </div>
            
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-32 border-2 border-border" data-testid="status-filter">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Status</SelectItem>
                <SelectItem value="DRAFT">Draft</SelectItem>
                <SelectItem value="READY">Ready</SelectItem>
                <SelectItem value="PUBLISHED">Published</SelectItem>
                <SelectItem value="ERROR">Error</SelectItem>
              </SelectContent>
            </Select>
            
            <Select value={typeFilter} onValueChange={setTypeFilter}>
              <SelectTrigger className="w-32 border-2 border-border" data-testid="type-filter">
                <SelectValue placeholder="Type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Types</SelectItem>
                <SelectItem value="WHL">Wheels</SelectItem>
                <SelectItem value="TRK">Trucks</SelectItem>
                <SelectItem value="DCK">Decks</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* Drafts List */}
        {loading ? (
          <div className="text-center py-12 font-mono">Loading...</div>
        ) : drafts.length === 0 ? (
          <div className="bg-card border-2 border-border p-12 text-center shadow-hard">
            <FileText className="w-12 h-12 mx-auto mb-4 text-muted-foreground" />
            <h3 className="font-heading font-bold text-xl uppercase mb-2">No drafts yet</h3>
            <p className="text-muted-foreground font-mono text-sm mb-4">
              Create your first eBay listing draft
            </p>
            <Button
              onClick={() => navigate("/new")}
              className="bg-primary text-primary-foreground border-2 border-border shadow-hard hover:translate-y-[2px] hover:shadow-hard-sm transition-all uppercase font-bold tracking-wider"
            >
              <Plus className="w-4 h-4 mr-2" />
              New Draft
            </Button>
          </div>
        ) : (
          <div className="space-y-3">
            {drafts.map((draft) => {
              const statusStyle = STATUS_STYLES[draft.status] || STATUS_STYLES.DRAFT;
              const StatusIcon = statusStyle.icon;
              const itemType = ITEM_TYPES[draft.item_type] || { label: draft.item_type, icon: "📦" };
              
              return (
                <div
                  key={draft.id}
                  onClick={() => navigate(`/draft/${draft.id}`)}
                  className="bg-card border-2 border-border p-4 shadow-hard hover:translate-y-[2px] hover:shadow-hard-sm transition-all cursor-pointer group"
                  data-testid={`draft-item-${draft.id}`}
                >
                  <div className="flex items-center gap-4">
                    {/* Thumbnail */}
                    <div className="w-16 h-16 bg-muted border-2 border-border flex-shrink-0 overflow-hidden">
                      {draft.image_urls?.[0] ? (
                        <img 
                          src={draft.image_urls[0].startsWith('http') ? draft.image_urls[0] : `${process.env.REACT_APP_BACKEND_URL}${draft.image_urls[0]}`}
                          alt={draft.title || draft.sku}
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center text-2xl">
                          {itemType.icon}
                        </div>
                      )}
                    </div>
                    
                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-mono text-sm font-medium">{draft.sku}</span>
                        <Badge className={`${statusStyle.bg} ${statusStyle.text} border-2 border-border uppercase text-[10px] font-bold px-2`}>
                          <StatusIcon className="w-3 h-3 mr-1" />
                          {draft.status}
                        </Badge>
                        <Badge variant="outline" className="border-2 border-border uppercase text-[10px] font-bold">
                          {itemType.label}
                        </Badge>
                      </div>
                      <h3 className="font-heading font-bold truncate">
                        {draft.title || "Untitled Draft"}
                      </h3>
                      <p className="text-sm text-muted-foreground font-mono">
                        ${draft.price?.toFixed(2) || "0.00"} · {new Date(draft.created_at).toLocaleDateString()}
                      </p>
                    </div>
                    
                    {/* Actions */}
                    <div 
                      className="flex items-center gap-2"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          e.preventDefault();
                          handleDelete(draft.id, e);
                        }}
                        className="p-2 text-destructive hover:bg-destructive/10 rounded transition-colors"
                        data-testid={`delete-draft-${draft.id}`}
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                  
                  {draft.status === "ERROR" && draft.error_message && (
                    <div className="mt-3 p-2 bg-red-50 border-2 border-red-200 text-red-700 text-xs font-mono">
                      {draft.error_message}
                    </div>
                  )}
                  
                  {draft.status === "PUBLISHED" && draft.listing_id && (
                    <div className="mt-3 flex items-center gap-2">
                      <a
                        href={`https://www.sandbox.ebay.com/itm/${draft.listing_id}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        className="inline-flex items-center gap-1 px-3 py-1 bg-green-100 text-green-700 text-xs font-mono border-2 border-green-300 hover:bg-green-200 transition-colors"
                      >
                        <ExternalLink className="w-3 h-3" />
                        View on eBay #{draft.listing_id}
                      </a>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
