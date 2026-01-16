import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import api from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
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
  ArrowLeft, Save, CheckCircle, Send, RefreshCw,
  AlertCircle, Clock, Circle, Plus, X, Lock, Eye, Wand2
} from "lucide-react";

const CONDITIONS = [
  { value: "NEW", label: "New" },
  { value: "LIKE_NEW", label: "Like New" },
  { value: "USED_EXCELLENT", label: "Used - Excellent" },
  { value: "USED_GOOD", label: "Used - Good" },
  { value: "USED_ACCEPTABLE", label: "Used - Acceptable" },
  { value: "FOR_PARTS_OR_NOT_WORKING", label: "For Parts" },
];

const STATUS_STYLES = {
  DRAFT: { bg: "bg-gray-200", text: "text-black", icon: Clock },
  READY: { bg: "bg-amber-400", text: "text-black", icon: Circle },
  PUBLISHED: { bg: "bg-green-500", text: "text-white", icon: CheckCircle },
  ERROR: { bg: "bg-red-500", text: "text-white", icon: AlertCircle },
};

// ============ TITLE BUILDER ============
const FILLER_WORDS = ["Unknown", "N/A", "(Unknown)", "undefined", "null", "", "assumed", "Vintage"];

const cleanValue = (val) => {
  if (!val) return null;
  const trimmed = String(val).trim();
  if (FILLER_WORDS.some(fw => trimmed.toLowerCase() === fw.toLowerCase())) return null;
  if (trimmed.length === 0) return null;
  return trimmed;
};

const buildEbayTitle = (itemType, aspects) => {
  if (!aspects) return "";
  
  const brand = cleanValue(aspects.Brand);
  const model = cleanValue(aspects.Model);
  const era = cleanValue(aspects.Era) || cleanValue(aspects.Decade);
  const size = cleanValue(aspects.Size);
  const color = cleanValue(aspects.Color);
  const durometer = cleanValue(aspects.Durometer);
  const ogNos = cleanValue(aspects.OG) || cleanValue(aspects.NOS) || cleanValue(aspects["OG/NOS"]);
  const series = cleanValue(aspects.Series);
  
  let parts = [];
  
  switch (itemType) {
    case "WHL": // Wheels
      if (brand) parts.push(brand);
      if (model) parts.push(model);
      if (era) parts.push(era);
      if (ogNos) parts.push(ogNos);
      if (color) parts.push(color);
      if (size) parts.push(size.includes("mm") ? size : `${size}mm`);
      if (durometer) parts.push(durometer.includes("A") ? durometer : `${durometer}A`);
      parts.push("Skateboard Wheels");
      break;
      
    case "TRK": // Trucks
      if (brand) parts.push(brand);
      if (model) parts.push(model);
      if (size) parts.push(size);
      if (era) parts.push(era);
      if (ogNos) parts.push(ogNos);
      parts.push("Skateboard Trucks");
      break;
      
    case "DCK": // Decks
      if (brand) parts.push(brand);
      if (model || series) parts.push(model || series);
      if (era) parts.push(era);
      if (ogNos) parts.push(ogNos);
      if (size) parts.push(size.includes('"') || size.includes("in") ? size : `${size}"`);
      parts.push("Skateboard Deck");
      break;
      
    default:
      if (brand) parts.push(brand);
      if (model) parts.push(model);
      if (era) parts.push(era);
      parts.push("Skateboard Part");
  }
  
  // Build title and clean up
  let title = parts.join(" ");
  
  // Remove multiple spaces
  title = title.replace(/\s+/g, " ").trim();
  
  // Remove double commas or weird punctuation
  title = title.replace(/,\s*,/g, ",").replace(/\s+,/g, ",");
  
  // Truncate to 80 chars if needed, removing less important words first
  if (title.length > 80) {
    // Try removing "Skateboard" first
    let shortened = title.replace(/Skateboard\s*/gi, "");
    if (shortened.length <= 80) {
      title = shortened;
    } else {
      // Just truncate
      title = title.substring(0, 77) + "...";
    }
  }
  
  return title;
};

// Key aspects that trigger title rebuild
const TITLE_TRIGGER_KEYS = ["Brand", "Model", "Size", "Era", "Decade", "Color", "Durometer", "OG", "NOS", "OG/NOS", "Series"];

export default function DraftEditor() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  
  const [draft, setDraft] = useState(null);
  const [title, setTitle] = useState("");
  const [titleManuallyEdited, setTitleManuallyEdited] = useState(false);
  const [description, setDescription] = useState("");
  const [aspects, setAspects] = useState({});
  const [condition, setCondition] = useState("USED_GOOD");
  const [categoryId, setCategoryId] = useState("");
  const [price, setPrice] = useState("");
  const [newAspectKey, setNewAspectKey] = useState("");
  const [newAspectValue, setNewAspectValue] = useState("");

  useEffect(() => {
    fetchDraft();
  }, [id]);

  // Auto-update title when aspects change (if not manually edited)
  useEffect(() => {
    if (!titleManuallyEdited && draft?.item_type && aspects) {
      const hasRelevantAspects = TITLE_TRIGGER_KEYS.some(key => cleanValue(aspects[key]));
      if (hasRelevantAspects) {
        const newTitle = buildEbayTitle(draft.item_type, aspects);
        if (newTitle && newTitle !== title) {
          setTitle(newTitle);
        }
      }
    }
  }, [aspects, draft?.item_type, titleManuallyEdited]);

  const fetchDraft = async () => {
    try {
      const response = await api.get(`/drafts/${id}`);
      const data = response.data;
      setDraft(data);
      setTitle(data.title || "");
      setTitleManuallyEdited(data.title_manually_edited || false);
      setDescription(data.description || "");
      setAspects(data.aspects || {});
      setCondition(data.condition || "USED_GOOD");
      setCategoryId(data.category_id || "");
      setPrice(data.price?.toString() || "");
    } catch (error) {
      toast.error("Failed to load draft");
      navigate("/");
    } finally {
      setLoading(false);
    }
  };

  const handleTitleChange = (e) => {
    setTitle(e.target.value);
    setTitleManuallyEdited(true);
  };

  const handleRegenerateTitle = () => {
    if (draft?.item_type && aspects) {
      const newTitle = buildEbayTitle(draft.item_type, aspects);
      setTitle(newTitle);
      setTitleManuallyEdited(false);
      toast.success("Titolo rigenerato dagli specifics");
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.patch(`/drafts/${id}`, {
        title,
        title_manually_edited: titleManuallyEdited,
        description,
        aspects,
        condition,
        category_id: categoryId,
        price: parseFloat(price)
      });
      toast.success("Draft salvato");
      await fetchDraft();
    } catch (error) {
      toast.error("Errore nel salvataggio");
    } finally {
      setSaving(false);
    }
  };

  const handleMarkReady = async () => {
    setSaving(true);
    try {
      await api.patch(`/drafts/${id}`, { status: "READY" });
      toast.success("Draft marked as ready");
      await fetchDraft();
    } catch (error) {
      toast.error("Failed to update status");
    } finally {
      setSaving(false);
    }
  };

  const handlePublish = async () => {
    setPublishing(true);
    try {
      const response = await api.post(`/drafts/${id}/publish`);
      toast.success(`Published! Listing ID: ${response.data.listing_id || 'N/A'}`);
      await fetchDraft();
    } catch (error) {
      const detail = error.response?.data?.detail;
      if (detail?.errors) {
        detail.errors.forEach(err => toast.error(err));
      } else {
        toast.error(typeof detail === 'string' ? detail : "Publish failed");
      }
      await fetchDraft();
    } finally {
      setPublishing(false);
    }
  };

  const handlePreview = async () => {
    // Save first, then navigate to preview
    setSaving(true);
    try {
      await api.patch(`/drafts/${id}`, {
        title,
        title_manually_edited: titleManuallyEdited,
        description,
        aspects,
        condition,
        category_id: categoryId,
        price: parseFloat(price)
      });
      // Navigate to preview after successful save
      navigate(`/draft/${id}/preview`);
    } catch (error) {
      toast.error("Errore nel salvataggio prima della preview");
    } finally {
      setSaving(false);
    }
  };

  const handleRegenerate = async () => {
    setRegenerating(true);
    try {
      toast.loading("Rigenerazione contenuto...");
      await api.post(`/drafts/${id}/generate`);
      toast.dismiss();
      toast.success("Contenuto rigenerato");
      await fetchDraft();
    } catch (error) {
      toast.dismiss();
      toast.error("Rigenerazione fallita");
    } finally {
      setRegenerating(false);
    }
  };

  const handleAspectChange = (key, value) => {
    setAspects(prev => ({ ...prev, [key]: value }));
  };

  const addAspect = () => {
    if (newAspectKey && newAspectValue) {
      setAspects(prev => ({ ...prev, [newAspectKey]: newAspectValue }));
      setNewAspectKey("");
      setNewAspectValue("");
    }
  };

  const removeAspect = (key) => {
    setAspects(prev => {
      const newAspects = { ...prev };
      delete newAspects[key];
      return newAspects;
    });
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="font-mono">Loading...</div>
      </div>
    );
  }

  if (!draft) return null;

  const statusStyle = STATUS_STYLES[draft.status] || STATUS_STYLES.DRAFT;
  const StatusIcon = statusStyle.icon;
  const isPublished = draft.status === "PUBLISHED";
  const titleLength = title.length;
  const isTitleValid = titleLength <= 80;

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="bg-card border-b-2 border-border sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-4">
              <Link to="/" className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors">
                <ArrowLeft className="w-4 h-4" />
                <span className="font-bold text-sm uppercase tracking-wider">Back</span>
              </Link>
              <span className="font-mono text-sm">{draft.sku}</span>
              <Badge className={`${statusStyle.bg} ${statusStyle.text} border-2 border-border uppercase text-[10px] font-bold`}>
                <StatusIcon className="w-3 h-3 mr-1" />
                {draft.status}
              </Badge>
            </div>
            
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handlePreview}
                disabled={saving}
                className="border-2 border-border shadow-hard-sm hover:translate-y-[1px] hover:shadow-none transition-all uppercase font-bold text-xs tracking-wider"
                data-testid="preview-btn"
              >
                <Eye className="w-4 h-4 mr-2" />
                Preview
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleRegenerate}
                disabled={regenerating || isPublished}
                className="border-2 border-border shadow-hard-sm hover:translate-y-[1px] hover:shadow-none transition-all uppercase font-bold text-xs tracking-wider"
                data-testid="regenerate-btn"
              >
                <RefreshCw className={`w-4 h-4 mr-2 ${regenerating ? 'animate-spin' : ''}`} />
                Regenerate
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleSave}
                disabled={saving || isPublished}
                className="border-2 border-border shadow-hard-sm hover:translate-y-[1px] hover:shadow-none transition-all uppercase font-bold text-xs tracking-wider"
                data-testid="save-btn"
              >
                <Save className="w-4 h-4 mr-2" />
                Save
              </Button>
              {!isPublished && draft.status !== "READY" && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleMarkReady}
                  disabled={saving}
                  className="border-2 border-border shadow-hard-sm hover:translate-y-[1px] hover:shadow-none transition-all uppercase font-bold text-xs tracking-wider"
                  data-testid="mark-ready-btn"
                >
                  <CheckCircle className="w-4 h-4 mr-2" />
                  Mark Ready
                </Button>
              )}
              <Button
                size="sm"
                onClick={handlePublish}
                disabled={publishing || isPublished}
                className="bg-primary text-primary-foreground border-2 border-border shadow-hard-sm hover:translate-y-[1px] hover:shadow-none transition-all uppercase font-bold text-xs tracking-wider"
                data-testid="publish-btn"
              >
                <Send className="w-4 h-4 mr-2" />
                {publishing ? "Publishing..." : "Publish"}
              </Button>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Left Column - Images & Details */}
          <div className="space-y-6">
            {/* Images */}
            <div className="bg-card border-2 border-border p-4 shadow-hard">
              <h3 className="font-heading font-bold uppercase tracking-tight mb-4 border-b-2 border-border pb-2">Images</h3>
              {draft.image_urls?.length > 0 ? (
                <div className="grid grid-cols-2 gap-2">
                  {draft.image_urls.map((url, i) => (
                    <img 
                      key={i}
                      src={url.startsWith('http') ? url : `${process.env.REACT_APP_BACKEND_URL}${url}`}
                      alt={`Image ${i + 1}`}
                      className="w-full h-24 object-cover border-2 border-border"
                    />
                  ))}
                </div>
              ) : (
                <p className="text-muted-foreground font-mono text-sm">No images</p>
              )}
            </div>

            {/* Category & Price */}
            <div className="bg-card border-2 border-border p-4 shadow-hard space-y-4">
              <h3 className="font-heading font-bold uppercase tracking-tight border-b-2 border-border pb-2">Details</h3>
              
              <div className="space-y-2">
                <Label className="text-xs font-bold uppercase tracking-widest">Category ID</Label>
                <Input
                  value={categoryId}
                  onChange={(e) => setCategoryId(e.target.value)}
                  disabled={isPublished}
                  className="border-2 border-border font-mono"
                  data-testid="edit-category-input"
                />
              </div>
              
              <div className="space-y-2">
                <Label className="text-xs font-bold uppercase tracking-widest">Price (USD)</Label>
                <Input
                  type="number"
                  step="0.01"
                  value={price}
                  onChange={(e) => setPrice(e.target.value)}
                  disabled={isPublished}
                  className="border-2 border-border font-mono"
                  data-testid="edit-price-input"
                />
              </div>
              
              <div className="space-y-2">
                <Label className="text-xs font-bold uppercase tracking-widest">Condition</Label>
                <Select value={condition} onValueChange={setCondition} disabled={isPublished}>
                  <SelectTrigger className="border-2 border-border" data-testid="condition-select">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {CONDITIONS.map(c => (
                      <SelectItem key={c.value} value={c.value}>{c.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Shipping Info (Locked) */}
            <div className="bg-card border-2 border-border p-4 shadow-hard opacity-75">
              <div className="flex items-center gap-2 mb-4 border-b-2 border-border pb-2">
                <Lock className="w-4 h-4" />
                <h3 className="font-heading font-bold uppercase tracking-tight">Shipping & Returns</h3>
              </div>
              <div className="space-y-2 text-sm font-mono text-muted-foreground">
                <p>Europe (incl. UK, CH): $10</p>
                <p>USA + Canada: $25</p>
                <p>Rest of World: $45</p>
                <p className="border-t border-border pt-2 mt-2">Returns: 30 days, buyer pays return</p>
                <p>Handling: 2 business days</p>
              </div>
            </div>
          </div>

          {/* Right Column - Content Editor */}
          <div className="lg:col-span-2 space-y-6">
            {/* Error Message */}
            {draft.status === "ERROR" && draft.error_message && (
              <div className="bg-red-50 border-2 border-red-400 p-4 flex items-start gap-3">
                <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-bold text-red-800 uppercase text-sm tracking-wider">Error Details</p>
                  <p className="text-red-700 font-mono text-sm mt-1">{draft.error_message}</p>
                </div>
              </div>
            )}

            {/* Title */}
            <div className="bg-card border-2 border-border p-4 shadow-hard">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <Label className="text-xs font-bold uppercase tracking-widest">Title</Label>
                  {titleManuallyEdited && (
                    <Badge variant="outline" className="text-[9px] border-amber-400 text-amber-600">
                      Manual
                    </Badge>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={handleRegenerateTitle}
                    disabled={isPublished}
                    className="text-xs text-primary hover:underline flex items-center gap-1 disabled:opacity-50"
                    data-testid="regenerate-title-btn"
                  >
                    <Wand2 className="w-3 h-3" />
                    Regenerate title
                  </button>
                  <span className={`font-mono text-xs ${isTitleValid ? 'text-muted-foreground' : 'text-destructive font-bold'}`}>
                    {titleLength}/80
                  </span>
                </div>
              </div>
              <Input
                value={title}
                onChange={handleTitleChange}
                disabled={isPublished}
                className={`border-2 font-mono ${isTitleValid ? 'border-border' : 'border-destructive'}`}
                placeholder="eBay listing title (max 80 chars)"
                data-testid="edit-title-input"
              />
              {!isTitleValid && (
                <p className="text-destructive text-xs font-mono mt-1">Title exceeds 80 character limit</p>
              )}
              <p className="text-xs text-muted-foreground mt-2 font-mono">
                💡 Il titolo si aggiorna automaticamente quando modifichi Brand, Model, Size, Era negli Item Specifics.
              </p>
            </div>

            {/* Description */}
            <div className="bg-card border-2 border-border p-4 shadow-hard">
              <Label className="text-xs font-bold uppercase tracking-widest mb-2 block">Description</Label>
              <Textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                disabled={isPublished}
                rows={12}
                className="border-2 border-border font-mono text-sm"
                placeholder="Product description (HTML supported)"
                data-testid="edit-description-input"
              />
            </div>

            {/* Aspects */}
            <div className="bg-card border-2 border-border p-4 shadow-hard">
              <Label className="text-xs font-bold uppercase tracking-widest mb-4 block">
                Item Specifics
                <span className="text-muted-foreground font-normal ml-2">(modificali per aggiornare il titolo)</span>
              </Label>
              
              <div className="space-y-2 mb-4">
                {Object.entries(aspects).map(([key, value]) => {
                  const isKeyAspect = TITLE_TRIGGER_KEYS.includes(key);
                  return (
                    <div key={key} className={`flex items-center gap-2 p-2 border-2 border-border ${isKeyAspect ? 'bg-primary/5' : 'bg-muted'}`}>
                      <span className={`font-bold text-sm uppercase tracking-wider w-32 ${isKeyAspect ? 'text-primary' : ''}`}>
                        {key}
                        {isKeyAspect && <span className="text-[9px] ml-1">★</span>}
                      </span>
                      <Input
                        value={value}
                        onChange={(e) => handleAspectChange(key, e.target.value)}
                        disabled={isPublished}
                        className="flex-1 border-2 border-border font-mono text-sm h-8"
                        data-testid={`aspect-${key}`}
                      />
                      {!isPublished && (
                        <button
                          onClick={() => removeAspect(key)}
                          className="w-8 h-8 flex items-center justify-center bg-destructive text-white border-2 border-border hover:bg-destructive/80"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
              
              {!isPublished && (
                <div className="flex gap-2 pt-2 border-t-2 border-border">
                  <Input
                    value={newAspectKey}
                    onChange={(e) => setNewAspectKey(e.target.value)}
                    placeholder="Key (es. Brand)"
                    className="w-32 border-2 border-border font-mono text-sm"
                    data-testid="new-aspect-key"
                  />
                  <Input
                    value={newAspectValue}
                    onChange={(e) => setNewAspectValue(e.target.value)}
                    placeholder="Value"
                    className="flex-1 border-2 border-border font-mono text-sm"
                    data-testid="new-aspect-value"
                  />
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={addAspect}
                    disabled={!newAspectKey || !newAspectValue}
                    className="border-2 border-border shadow-hard-sm"
                    data-testid="add-aspect-btn"
                  >
                    <Plus className="w-4 h-4" />
                  </Button>
                </div>
              )}
            </div>

            {/* Published Info */}
            {isPublished && (
              <div className="bg-green-50 border-2 border-green-400 p-4">
                <div className="flex items-center gap-2 mb-2">
                  <CheckCircle className="w-5 h-5 text-green-600" />
                  <span className="font-bold text-green-800 uppercase tracking-wider">Published to eBay</span>
                </div>
                <div className="font-mono text-sm text-green-700 space-y-1">
                  {draft.offer_id && <p>Offer ID: {draft.offer_id}</p>}
                  {draft.listing_id && <p>Listing ID: {draft.listing_id}</p>}
                </div>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
