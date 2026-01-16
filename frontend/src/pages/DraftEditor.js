import { useState, useEffect } from "react";
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
  AlertCircle, Clock, Circle, Plus, X, Lock, Eye, Wand2, Sparkles
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
const FILLER_WORDS = ["Unknown", "N/A", "(Unknown)", "undefined", "null", "", "assumed", "estimate"];

// Keyword fillers in priority order (OG/NOS handled separately based on aspects)
const KEYWORD_FILLERS = ["Old School", "Vintage"];

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
  const size = cleanValue(aspects.Size) || cleanValue(aspects.Width);
  const color = cleanValue(aspects.Color);
  const durometer = cleanValue(aspects.Durometer);
  const series = cleanValue(aspects.Series);
  const itemTypeAspect = cleanValue(aspects["Item Type"]);
  const department = cleanValue(aspects.Department);
  
  // Handle OG/NOS - mutually exclusive
  const ogValue = cleanValue(aspects.OG);
  const nosValue = cleanValue(aspects.NOS);
  const ogNosValue = cleanValue(aspects["OG/NOS"]);
  const typeValue = cleanValue(aspects.Type);
  
  let ogNos = null;
  let hasOG = false;
  let hasNOS = false;
  
  // Check Type field for OG/NOS
  if (typeValue) {
    if (typeValue.toUpperCase() === "NOS" || typeValue.toUpperCase().includes("NOS")) {
      hasNOS = true;
      ogNos = "NOS";
    } else if (typeValue.toUpperCase() === "OG" || typeValue.toUpperCase().includes("OG")) {
      hasOG = true;
      ogNos = "OG";
    }
  }
  
  // Also check dedicated OG/NOS fields
  if (!hasNOS && !hasOG) {
    if (nosValue && (nosValue.toLowerCase() === "true" || nosValue.toLowerCase() === "yes" || nosValue === "NOS")) {
      ogNos = "NOS";
      hasNOS = true;
    } else if (ogValue && (ogValue.toLowerCase() === "true" || ogValue.toLowerCase() === "yes" || ogValue === "OG")) {
      ogNos = "OG";
      hasOG = true;
    } else if (ogNosValue) {
      ogNos = ogNosValue;
      if (ogNosValue.toUpperCase().includes("NOS")) hasNOS = true;
      if (ogNosValue.toUpperCase().includes("OG")) hasOG = true;
    }
  }
  
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
      
    case "APP": // Apparel
      if (brand) parts.push(brand);
      if (itemTypeAspect) parts.push(itemTypeAspect);
      if (size) parts.push(size);
      if (era) parts.push(era);
      if (color) parts.push(color);
      parts.push("Skateboard");
      if (!itemTypeAspect) {
        parts.push("Apparel");
      }
      break;
      
    default: // MISC
      if (brand) parts.push(brand);
      if (model || itemTypeAspect) parts.push(model || itemTypeAspect);
      if (era) parts.push(era);
      parts.push("Skateboard Part");
  }
  
  // Build base title and clean up
  let title = parts.join(" ");
  title = title.replace(/\s+/g, " ").trim();
  title = title.replace(/,\s*,/g, ",").replace(/\s+,/g, ",");
  
  // Check what specs are missing for keyword filler decision
  const missingImportantSpecs = !size || !durometer || !model;
  
  // Add keyword fillers if title < 70 chars and missing important specs
  if (title.length < 70 && missingImportantSpecs) {
    const titleLower = title.toLowerCase();
    
    // Try adding keyword fillers in priority order
    for (const keyword of KEYWORD_FILLERS) {
      // Don't add if already present in title
      if (titleLower.includes(keyword.toLowerCase())) continue;
      
      // Check if adding would exceed 80
      const potentialTitle = `${keyword} ${title}`;
      if (potentialTitle.length <= 80) {
        title = potentialTitle;
        // Check if we've reached target range (70-80)
        if (title.length >= 70) break;
      }
    }
    
    // Try adding OG or NOS if applicable and not already present
    if (title.length < 70) {
      if (hasNOS && !titleLower.includes("nos")) {
        const potentialTitle = title.replace("Skateboard", "NOS Skateboard");
        if (potentialTitle.length <= 80 && !title.includes("NOS")) {
          title = potentialTitle;
        }
      } else if (hasOG && !titleLower.includes(" og ") && !titleLower.includes("og ")) {
        const potentialTitle = title.replace("Skateboard", "OG Skateboard");
        if (potentialTitle.length <= 80 && !title.includes("OG")) {
          title = potentialTitle;
        }
      }
    }
  }
  
  // Hard limit: truncate to 80 chars
  if (title.length > 80) {
    let shortened = title.replace(/Skateboard\s*/gi, "");
    if (shortened.length <= 80) {
      title = shortened;
    } else {
      title = title.substring(0, 77) + "...";
    }
  }
  
  return title;
};

// ============ 90s STICKER LABEL DESCRIPTION BUILDER ============
const build90sDescription = (itemType, title, aspects, condition) => {
  if (!aspects || Object.keys(aspects).length === 0) return "";
  
  const cleanAspects = {};
  Object.entries(aspects).forEach(([k, v]) => {
    const clean = cleanValue(v);
    if (clean) cleanAspects[k] = clean;
  });
  
  if (Object.keys(cleanAspects).length === 0) return "";
  
  // Get era for sticker header
  const era = cleanAspects.Era || cleanAspects.Decade || "";
  const eraTag = era ? ` • ${era}` : "";
  
  // Build key details based on item type
  let keyDetailsOrder = [];
  
  switch (itemType) {
    case "APP":
      keyDetailsOrder = ["Brand", "Item Type", "Department", "Size", "Measurements", "Color", "Material", "Style", "Fit", "Country", "MPN", "UPC"];
      break;
    case "WHL":
      keyDetailsOrder = ["Brand", "Model", "Size", "Durometer", "Color", "Era", "Core", "Material", "Quantity", "MPN"];
      break;
    case "TRK":
      keyDetailsOrder = ["Brand", "Model", "Size", "Era", "Color", "Material", "Quantity", "MPN"];
      break;
    case "DCK":
      keyDetailsOrder = ["Brand", "Model", "Series", "Width", "Length", "Era", "Artist", "Type", "Material", "MPN"];
      break;
    default:
      keyDetailsOrder = ["Brand", "Item Type", "Era", "Size", "Color", "Material", "Notes"];
  }
  
  // Build key details HTML
  let keyDetailsHtml = "";
  keyDetailsOrder.forEach(key => {
    if (cleanAspects[key]) {
      keyDetailsHtml += `  <li><strong>${key}:</strong> ${cleanAspects[key]}</li>\n`;
    }
  });
  
  // Add any extra aspects not in the order
  Object.entries(cleanAspects).forEach(([key, value]) => {
    if (!keyDetailsOrder.includes(key) && key !== "Era" && key !== "Decade") {
      keyDetailsHtml += `  <li><strong>${key}:</strong> ${value}</li>\n`;
    }
  });
  
  // Collector intro based on type
  let intro = "";
  
  switch (itemType) {
    case "APP":
      intro = era 
        ? `A rare find for collectors of ${era} skateboard streetwear. Perfect for vintage enthusiasts or period-correct setups. Please check the photos and tags carefully.`
        : `Vintage skateboard apparel for collectors and enthusiasts. Please check the photos and tags carefully.`;
      break;
    case "WHL":
      intro = era
        ? `Classic ${era} skateboard wheels for the serious collector. Ideal for vintage builds, restorations, or period-correct setups. See photos for details.`
        : `Vintage skateboard wheels for collectors and riders who appreciate classic gear. See photos for details.`;
      break;
    case "TRK":
      intro = era
        ? `Original ${era} skateboard trucks. A must-have for vintage skateboard collectors and restoration projects.`
        : `Vintage skateboard trucks for collectors and enthusiasts. Great for restorations or display.`;
      break;
    case "DCK":
      intro = era
        ? `Vintage ${era} skateboard deck. A piece of skateboarding history perfect for collectors or wall display.`
        : `Classic skateboard deck for collectors and enthusiasts. Check all photos for condition details.`;
      break;
    default:
      intro = `Vintage skateboard item for collectors and enthusiasts. See photos for full details.`;
  }
  
  // Condition text
  const conditionLabel = condition ? CONDITIONS.find(c => c.value === condition)?.label || condition : "New";
  let conditionSection = `<strong>${conditionLabel}.</strong> Please review all photos carefully as they are part of the description.`;
  
  // Add NOS note if applicable and condition is NEW
  if (condition === "NEW" && (cleanAspects.Type === "NOS" || cleanAspects.NOS === "true" || cleanAspects.NOS === "Yes")) {
    conditionSection += ` May show light storage/shelf wear.`;
  }
  
  // Build 90s sticker label HTML
  const description = `<div style="font-family: Arial, Helvetica, sans-serif; font-size: 14px; line-height: 1.45; color: #111; max-width: 800px;">

<div style="display: inline-block; border: 1px solid #111; padding: 6px 10px; font-family: 'Courier New', Courier, monospace; letter-spacing: 1px; margin-bottom: 16px;">
[ OLD SCHOOL SKATE ]${eraTag}
</div>

<p style="margin: 12px 0;">${intro}</p>

<h2 style="font-size: 12px; letter-spacing: 1px; margin: 18px 0 6px; text-transform: uppercase; border-bottom: 1px solid #111; padding-bottom: 4px;">KEY DETAILS</h2>
<ul style="margin: 0; padding-left: 20px;">
${keyDetailsHtml}</ul>

<h2 style="font-size: 12px; letter-spacing: 1px; margin: 18px 0 6px; text-transform: uppercase; border-bottom: 1px solid #111; padding-bottom: 4px;">CONDITION</h2>
<p style="margin: 8px 0;">${conditionSection}</p>

<h2 style="font-size: 12px; letter-spacing: 1px; margin: 18px 0 6px; text-transform: uppercase; border-bottom: 1px solid #111; padding-bottom: 4px;">INFO</h2>
<p style="margin: 8px 0;">Questions? Feel free to message—happy to help.</p>
<p style="margin: 8px 0;">Ships from Milan, Italy. Combined shipping available—please message before purchase.</p>
<p style="margin: 8px 0;">International buyers: import duties/taxes are not included and are the buyer's responsibility.</p>
<p style="margin: 8px 0;"><strong>Thanks for looking!</strong></p>

</div>`;
  
  return description.trim();
};

// Key aspects that trigger title/description rebuild
const TITLE_TRIGGER_KEYS = ["Brand", "Model", "Size", "Width", "Era", "Decade", "Color", "Durometer", "OG", "NOS", "OG/NOS", "Type", "Series", "Item Type", "Department"];

export default function DraftEditor() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [autoFilling, setAutoFilling] = useState(false);
  
  const [draft, setDraft] = useState(null);
  const [title, setTitle] = useState("");
  const [titleManuallyEdited, setTitleManuallyEdited] = useState(false);
  const [description, setDescription] = useState("");
  const [descriptionManuallyEdited, setDescriptionManuallyEdited] = useState(false);
  const [aspects, setAspects] = useState({});
  const [autoFilledAspects, setAutoFilledAspects] = useState([]);
  const [condition, setCondition] = useState("NEW");
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

  // Auto-update description when title or aspects change (if not manually edited)
  useEffect(() => {
    if (!descriptionManuallyEdited && draft?.item_type && aspects) {
      const hasRelevantAspects = TITLE_TRIGGER_KEYS.some(key => cleanValue(aspects[key]));
      if (hasRelevantAspects || title) {
        const newDescription = build90sDescription(draft.item_type, title, aspects, condition);
        if (newDescription && newDescription !== description) {
          setDescription(newDescription);
        }
      }
    }
  }, [aspects, title, condition, draft?.item_type, descriptionManuallyEdited]);

  const fetchDraft = async () => {
    try {
      const response = await api.get(`/drafts/${id}`);
      const data = response.data;
      setDraft(data);
      setTitle(data.title || "");
      setTitleManuallyEdited(data.title_manually_edited || false);
      setDescription(data.description || "");
      setDescriptionManuallyEdited(data.description_manually_edited || false);
      setAspects(data.aspects || {});
      setAutoFilledAspects(data.auto_filled_aspects || []);
      setCondition(data.condition || "NEW");
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

  const handleDescriptionChange = (e) => {
    setDescription(e.target.value);
    setDescriptionManuallyEdited(true);
  };

  const handleRegenerateTitle = () => {
    if (draft?.item_type && aspects) {
      const newTitle = buildEbayTitle(draft.item_type, aspects);
      setTitle(newTitle);
      setTitleManuallyEdited(false);
      toast.success("Titolo rigenerato dagli specifics");
    }
  };

  const handleRegenerateDescription = () => {
    if (draft?.item_type) {
      const newDescription = build90sDescription(draft.item_type, title, aspects, condition);
      setDescription(newDescription);
      setDescriptionManuallyEdited(false);
      toast.success("Description rigenerata");
    }
  };

  const handleAutoFillAspects = async () => {
    setAutoFilling(true);
    try {
      toast.loading("Analyzing images...");
      const response = await api.post(`/drafts/${id}/autofill_aspects`);
      toast.dismiss();
      
      const { extracted_aspects, auto_filled_keys } = response.data;
      
      // Update local state
      setAspects(response.data.draft.aspects || {});
      setAutoFilledAspects(response.data.draft.auto_filled_aspects || []);
      
      if (auto_filled_keys.length > 0) {
        toast.success(`Auto-filled ${auto_filled_keys.length} aspects: ${auto_filled_keys.join(", ")}`);
      } else {
        toast.info("No new aspects could be extracted from images");
      }
      
      await fetchDraft();
    } catch (error) {
      toast.dismiss();
      toast.error(error.response?.data?.detail || "Auto-fill failed");
    } finally {
      setAutoFilling(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    
    // Auto-truncate title if over 80 chars
    let titleToSave = title;
    if (title.length > 80) {
      titleToSave = title.substring(0, 77) + "...";
      setTitle(titleToSave);
      toast.warning("Titolo troncato a 80 caratteri");
    }
    
    try {
      await api.patch(`/drafts/${id}`, {
        title: titleToSave,
        title_manually_edited: titleManuallyEdited,
        description,
        description_manually_edited: descriptionManuallyEdited,
        aspects,
        auto_filled_aspects: autoFilledAspects,
        condition,
        category_id: categoryId,
        price: parseFloat(price) || 0
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
    setSaving(true);
    try {
      await api.patch(`/drafts/${id}`, {
        title,
        title_manually_edited: titleManuallyEdited,
        description,
        description_manually_edited: descriptionManuallyEdited,
        aspects,
        auto_filled_aspects: autoFilledAspects,
        condition,
        category_id: categoryId,
        price: parseFloat(price) || 0
      });
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
    // Remove from auto-filled list when manually edited
    if (autoFilledAspects.includes(key)) {
      setAutoFilledAspects(prev => prev.filter(k => k !== key));
    }
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
    // Also remove from auto-filled list
    setAutoFilledAspects(prev => prev.filter(k => k !== key));
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

  // Get suggested aspects based on item type
  const getSuggestedAspects = () => {
    switch (draft.item_type) {
      case "APP":
        return ["Brand", "Item Type", "Department", "Size", "Measurements", "Color", "Material", "Style", "Fit", "Era"];
      case "WHL":
        return ["Brand", "Model", "Size", "Durometer", "Color", "Era", "Core", "Material", "Quantity"];
      case "TRK":
        return ["Brand", "Model", "Size", "Era", "Color", "Material", "Quantity"];
      case "DCK":
        return ["Brand", "Model", "Series", "Width", "Length", "Era", "Artist", "Type"];
      default:
        return ["Brand", "Item Type", "Era", "Size", "Color", "Material"];
    }
  };

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
              <Badge variant="outline" className="border-2 border-border uppercase text-[10px] font-bold">
                {draft.item_type}
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
                <div className="flex items-center gap-3">
                  <button
                    onClick={handleRegenerateTitle}
                    disabled={isPublished}
                    className="text-xs text-primary hover:underline flex items-center gap-1 disabled:opacity-50"
                    data-testid="regenerate-title-btn"
                  >
                    <Wand2 className="w-3 h-3" />
                    Regenerate
                  </button>
                  <div className="flex items-center gap-1">
                    <span className={`font-mono text-xs font-bold ${
                      titleLength > 80 
                        ? 'text-destructive' 
                        : titleLength >= 70 
                          ? 'text-green-600' 
                          : 'text-muted-foreground'
                    }`}>
                      {titleLength}
                    </span>
                    <span className="font-mono text-xs text-muted-foreground">/80</span>
                    {titleLength >= 70 && titleLength <= 80 && (
                      <span className="text-[9px] text-green-600 font-bold ml-1">✓</span>
                    )}
                  </div>
                </div>
              </div>
              <Input
                value={title}
                onChange={handleTitleChange}
                disabled={isPublished}
                className={`border-2 font-mono ${
                  titleLength > 80 
                    ? 'border-destructive bg-red-50' 
                    : titleLength >= 70 
                      ? 'border-green-500' 
                      : 'border-border'
                }`}
                placeholder="eBay listing title (max 80 chars)"
                data-testid="edit-title-input"
              />
              {titleLength > 80 && (
                <p className="text-destructive text-xs font-mono mt-1">
                  ⚠️ Titolo supera 80 caratteri - verrà troncato automaticamente al salvataggio
                </p>
              )}
              {titleLength < 70 && titleLength > 0 && (
                <p className="text-muted-foreground text-xs font-mono mt-1">
                  💡 Target: 70-80 caratteri per migliore visibilità eBay
                </p>
              )}
            </div>

            {/* Description */}
            <div className="bg-card border-2 border-border p-4 shadow-hard">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <Label className="text-xs font-bold uppercase tracking-widest">Description</Label>
                  {descriptionManuallyEdited && (
                    <Badge variant="outline" className="text-[9px] border-amber-400 text-amber-600">
                      Manual
                    </Badge>
                  )}
                </div>
                <button
                  onClick={handleRegenerateDescription}
                  disabled={isPublished}
                  className="text-xs text-primary hover:underline flex items-center gap-1 disabled:opacity-50"
                  data-testid="regenerate-description-btn"
                >
                  <Wand2 className="w-3 h-3" />
                  Regenerate description
                </button>
              </div>
              <Textarea
                value={description}
                onChange={handleDescriptionChange}
                disabled={isPublished}
                rows={12}
                className="border-2 border-border font-mono text-sm"
                placeholder="Product description (HTML supported)"
                data-testid="edit-description-input"
              />
              <p className="text-xs text-muted-foreground mt-2 font-mono">
                💡 La description si aggiorna automaticamente quando modifichi Title o Item Specifics (formato 90s sticker label).
              </p>
            </div>

            {/* Aspects */}
            <div className="bg-card border-2 border-border p-4 shadow-hard">
              <div className="flex items-center justify-between mb-4">
                <Label className="text-xs font-bold uppercase tracking-widest">
                  Item Specifics
                  <span className="text-muted-foreground font-normal ml-2">({draft.item_type})</span>
                </Label>
                {!isPublished && draft.image_urls?.length > 0 && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleAutoFillAspects}
                    disabled={autoFilling}
                    className="border-2 border-border shadow-hard-sm hover:translate-y-[1px] hover:shadow-none transition-all text-xs"
                    data-testid="autofill-aspects-btn"
                  >
                    <Sparkles className={`w-3 h-3 mr-1 ${autoFilling ? 'animate-pulse' : ''}`} />
                    {autoFilling ? "Analyzing..." : "Auto-fill specifics"}
                  </Button>
                )}
              </div>
              
              {/* Suggested aspects hint */}
              <div className="mb-4 p-2 bg-muted border border-border text-xs font-mono text-muted-foreground">
                <strong>Campi suggeriti per {draft.item_type}:</strong> {getSuggestedAspects().join(", ")}
              </div>
              
              <div className="space-y-2 mb-4">
                {Object.entries(aspects).map(([key, value]) => {
                  const isKeyAspect = TITLE_TRIGGER_KEYS.includes(key);
                  const isAutoFilled = autoFilledAspects.includes(key);
                  return (
                    <div key={key} className={`flex items-center gap-2 p-2 border-2 border-border ${isKeyAspect ? 'bg-primary/5' : 'bg-muted'}`}>
                      <div className="w-32 flex items-center gap-1">
                        <span className={`font-bold text-sm uppercase tracking-wider ${isKeyAspect ? 'text-primary' : ''}`}>
                          {key}
                        </span>
                        {isKeyAspect && <span className="text-[9px]">★</span>}
                        {isAutoFilled && (
                          <Badge variant="outline" className="text-[8px] border-cyan-400 text-cyan-600 px-1 py-0">
                            auto
                          </Badge>
                        )}
                      </div>
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
