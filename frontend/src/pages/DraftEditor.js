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
  AlertCircle, Clock, Circle, Plus, X, Lock, Eye, Wand2, Sparkles, ExternalLink
} from "lucide-react";

const CONDITIONS = [
  { value: "NEW", label: "New" },
  { value: "LIKE_NEW", label: "Like New" },
  { value: "USED_EXCELLENT", label: "Used - Excellent" },
  { value: "USED_GOOD", label: "Used - Good" },
  { value: "USED_ACCEPTABLE", label: "Used - Acceptable" },
  { value: "FOR_PARTS_OR_NOT_WORKING", label: "For Parts" },
];

const ERA_OPTIONS = [
  { value: "1970s", label: "1970s" },
  { value: "1980s", label: "1980s" },
  { value: "1990s", label: "1990s" },
  { value: "2000s", label: "2000s" },
  { value: "1980s-1990s", label: "1980s–1990s" },
  { value: "1970s-1980s", label: "1970s–1980s" },
];

const STATUS_STYLES = {
  DRAFT: { bg: "bg-gray-200", text: "text-black", icon: Clock },
  READY: { bg: "bg-amber-400", text: "text-black", icon: Circle },
  PUBLISHED: { bg: "bg-green-500", text: "text-white", icon: CheckCircle },
  ERROR: { bg: "bg-red-500", text: "text-white", icon: AlertCircle },
};

// ============ TITLE BUILDER ============
const FILLER_WORDS = ["Unknown", "N/A", "(Unknown)", "undefined", "null", "", "assumed", "estimate"];

// Keyword fillers in priority order for reaching 70-80 char target
const KEYWORD_FILLERS_PREFIX = ["Vintage", "Old School", "Classic", "Rare", "Original"];
const KEYWORD_FILLERS_SUFFIX = ["Set", "Pair", "- Great Condition", "- Collector Item"];

const cleanValue = (val) => {
  if (!val) return null;
  const trimmed = String(val).trim();
  if (FILLER_WORDS.some(fw => trimmed.toLowerCase() === fw.toLowerCase())) return null;
  if (trimmed.length === 0) return null;
  return trimmed;
};

const buildEbayTitle = (itemType, coreDetails, aspects) => {
  // Merge core details with aspects for title building
  const merged = { ...aspects, ...coreDetails };
  
  const brand = cleanValue(merged.brand) || cleanValue(merged.Brand);
  const model = cleanValue(merged.model) || cleanValue(merged.Model);
  const era = cleanValue(merged.era) || cleanValue(merged.Era) || cleanValue(merged.Decade);
  const size = cleanValue(merged.size) || cleanValue(merged.Size) || cleanValue(merged.Width);
  const color = cleanValue(merged.color) || cleanValue(merged.Color);
  const durometer = cleanValue(merged.Durometer);
  const series = cleanValue(merged.Series);
  const itemTypeAspect = cleanValue(merged["Item Type"]);
  
  // Handle OG/NOS
  const typeValue = cleanValue(merged.Type);
  let ogNos = null;
  let hasOG = false;
  let hasNOS = false;
  
  if (typeValue) {
    if (typeValue.toUpperCase().includes("NOS")) {
      hasNOS = true;
      ogNos = "NOS";
    } else if (typeValue.toUpperCase().includes("OG")) {
      hasOG = true;
      ogNos = "OG";
    }
  }
  
  let parts = [];
  
  switch (itemType) {
    case "WHL":
      if (brand) parts.push(brand);
      if (model) parts.push(model);
      if (era) parts.push(era);
      if (ogNos) parts.push(ogNos);
      if (color) parts.push(color);
      if (size) parts.push(size.includes("mm") ? size : `${size}mm`);
      if (durometer) parts.push(durometer.includes("A") ? durometer : `${durometer}A`);
      parts.push("Skateboard Wheels");
      break;
      
    case "TRK":
      if (brand) parts.push(brand);
      if (model) parts.push(model);
      if (size) parts.push(size);
      if (era) parts.push(era);
      if (ogNos) parts.push(ogNos);
      parts.push("Skateboard Trucks");
      break;
      
    case "DCK":
      if (brand) parts.push(brand);
      if (model || series) parts.push(model || series);
      if (era) parts.push(era);
      if (ogNos) parts.push(ogNos);
      if (size) parts.push(size.includes('"') || size.includes("in") ? size : `${size}"`);
      parts.push("Skateboard Deck");
      break;
      
    case "APP":
      if (brand) parts.push(brand);
      if (itemTypeAspect) parts.push(itemTypeAspect);
      if (size) parts.push(size);
      if (era) parts.push(era);
      if (color) parts.push(color);
      parts.push("Skateboard");
      if (!itemTypeAspect) parts.push("Apparel");
      break;
      
    default:
      if (brand) parts.push(brand);
      if (model || itemTypeAspect) parts.push(model || itemTypeAspect);
      if (era) parts.push(era);
      parts.push("Skateboard Part");
  }
  
  let title = parts.join(" ").replace(/\s+/g, " ").trim();
  
  // STEP 1: Add prefix keywords to reach 70 chars (if under)
  if (title.length < 70) {
    const titleLower = title.toLowerCase();
    for (const keyword of KEYWORD_FILLERS_PREFIX) {
      if (titleLower.includes(keyword.toLowerCase())) continue;
      const potentialTitle = `${keyword} ${title}`;
      if (potentialTitle.length <= 80) {
        title = potentialTitle;
        if (title.length >= 70) break;
      }
    }
  }
  
  // STEP 2: Add OG/NOS if applicable and still under 70
  if (title.length < 70) {
    const titleLower = title.toLowerCase();
    if (hasNOS && !titleLower.includes("nos")) {
      const potentialTitle = title.replace("Skateboard", "NOS Skateboard");
      if (potentialTitle.length <= 80) title = potentialTitle;
    } else if (hasOG && !titleLower.includes(" og ")) {
      const potentialTitle = title.replace("Skateboard", "OG Skateboard");
      if (potentialTitle.length <= 80) title = potentialTitle;
    }
  }
  
  // STEP 3: Add suffix keywords if still under 70
  if (title.length < 70) {
    for (const suffix of KEYWORD_FILLERS_SUFFIX) {
      const potentialTitle = `${title} ${suffix}`;
      if (potentialTitle.length >= 70 && potentialTitle.length <= 80) {
        title = potentialTitle;
        break;
      } else if (potentialTitle.length < 70) {
        title = potentialTitle;
      }
    }
  }
  
  // STEP 4: If still under 70, pad with descriptive text
  if (title.length < 70) {
    const padding = [
      "- Vintage Skateboarding",
      "- Skate History",
      "- 80s 90s Style",
      "- Retro Skate"
    ];
    for (const pad of padding) {
      const potentialTitle = `${title} ${pad}`;
      if (potentialTitle.length >= 70 && potentialTitle.length <= 80) {
        title = potentialTitle;
        break;
      }
    }
  }
  
  // STEP 5: Final padding if still under 70 (rare case)
  if (title.length < 70) {
    const needed = 70 - title.length;
    const fillers = ["Authentic", "Genuine", "USA", "Pro", "Team"];
    for (const filler of fillers) {
      if (title.length + filler.length + 1 <= 80) {
        title = `${filler} ${title}`;
        if (title.length >= 70) break;
      }
    }
  }
  
  // Hard limit: truncate to 80 chars if over
  if (title.length > 80) {
    // Try removing "Skateboard" word to save space
    let shortened = title.replace(/Skateboard\s*/gi, "").trim();
    if (shortened.length >= 70 && shortened.length <= 80) {
      title = shortened;
    } else {
      // Truncate with ellipsis
      title = title.substring(0, 77) + "...";
    }
  }
  
  return title;
};

// ============ 90s STICKER LABEL DESCRIPTION BUILDER ============
const build90sDescription = (itemType, coreDetails, aspects, condition) => {
  // Merge core details with aspects (excluding Model and Color)
  const merged = { ...aspects };
  if (coreDetails.brand) merged.Brand = coreDetails.brand;
  // Model and Color are excluded from description
  if (coreDetails.size) merged.Size = coreDetails.size;
  if (coreDetails.era) merged.Era = coreDetails.era;
  
  // Fields to exclude from description
  const excludedFields = ["Model", "Color", "Type", "Item Type", "Material", "Notes", "Decade"];
  
  // Filter out empty values and excluded fields
  const cleanAspects = {};
  Object.entries(merged).forEach(([k, v]) => {
    if (excludedFields.includes(k)) return;
    const clean = cleanValue(v);
    if (clean) cleanAspects[k] = clean;
  });
  
  if (Object.keys(cleanAspects).length === 0) return "";
  
  const era = cleanAspects.Era || cleanAspects.Decade || "";
  const eraTag = era ? ` • ${era}` : "";
  
  // Key details order by type (Model and Color removed)
  let keyDetailsOrder = [];
  switch (itemType) {
    case "APP":
      keyDetailsOrder = ["Brand", "Department", "Size", "Measurements", "Style", "Fit"];
      break;
    case "WHL":
      keyDetailsOrder = ["Brand", "Size", "Durometer", "Era", "Quantity"];
      break;
    case "TRK":
      keyDetailsOrder = ["Brand", "Size", "Era", "Quantity"];
      break;
    case "DCK":
      keyDetailsOrder = ["Brand", "Series", "Width", "Length", "Era", "Artist"];
      break;
    default:
      keyDetailsOrder = ["Brand", "Era", "Size"];
  }
  
  // Build key details HTML
  let keyDetailsHtml = "";
  keyDetailsOrder.forEach(key => {
    if (cleanAspects[key]) {
      keyDetailsHtml += `  <li><strong>${key}:</strong> ${cleanAspects[key]}</li>\n`;
    }
  });
  
  // Add extra aspects (excluding already shown and excluded fields)
  Object.entries(cleanAspects).forEach(([key, value]) => {
    if (!keyDetailsOrder.includes(key) && key !== "Era" && key !== "Decade") {
      keyDetailsHtml += `  <li><strong>${key}:</strong> ${value}</li>\n`;
    }
  });
  
  // Collector intro
  let intro = "";
  switch (itemType) {
    case "APP":
      intro = era 
        ? `A rare find for collectors of ${era} skateboard streetwear. Perfect for vintage enthusiasts or period-correct setups. This piece captures the authentic style and culture of the golden era of skateboarding. Please check the photos and tags carefully for sizing and condition details.`
        : `Vintage skateboard apparel for collectors and enthusiasts. A true piece of skateboarding history that represents the culture and style of the era. Please check the photos and tags carefully for sizing and condition details.`;
      break;
    case "WHL":
      intro = era
        ? `Classic ${era} skateboard wheels for the serious collector. These wheels represent the golden age of skateboarding and are ideal for vintage builds, restorations, or period-correct setups. Hard to find in this condition. See all photos for complete details.`
        : `Vintage skateboard wheels for collectors and riders who appreciate classic gear. These original wheels are becoming increasingly rare and are perfect for restoration projects or as collectibles. See all photos for complete details.`;
      break;
    case "TRK":
      intro = era
        ? `Original ${era} skateboard trucks - a true piece of skateboarding history. These trucks are a must-have for vintage skateboard collectors, restoration projects, or anyone building a period-correct setup. Increasingly difficult to find in good condition.`
        : `Vintage skateboard trucks for collectors and enthusiasts. These original trucks represent the craftsmanship and design of classic skateboarding. Great for restorations, display, or completing a vintage setup.`;
      break;
    case "DCK":
      intro = era
        ? `Vintage ${era} skateboard deck - an authentic piece of skateboarding history. Perfect for serious collectors, wall display, or museum-quality setups. These decks capture the art and culture of skateboarding's most influential era. Check all photos for graphics and condition details.`
        : `Classic skateboard deck for collectors and enthusiasts. This original deck represents the artistry and craftsmanship of vintage skateboarding. Perfect for display or as a centerpiece of any skateboard collection. Check all photos for graphics and condition details.`;
      break;
    default:
      intro = `Vintage skateboard item for collectors and enthusiasts. This authentic piece represents the history and culture of skateboarding. Hard to find and perfect for any serious collection. See all photos for complete details.`;
  }
  
  // Condition text
  const conditionLabel = condition ? CONDITIONS.find(c => c.value === condition)?.label || condition : "New";
  let conditionSection = `<strong>${conditionLabel}.</strong> Please review all photos carefully as they are part of the description and show the exact item you will receive.`;
  
  if (condition === "NEW" && (cleanAspects.Type === "NOS" || era)) {
    conditionSection += ` Being vintage/NOS, may show light storage or shelf wear consistent with age.`;
  }
  
  // Get brand for personalized message
  const brandName = cleanAspects.Brand || "this item";
  
  return `<div style="font-family: Arial, Helvetica, sans-serif; font-size: 14px; line-height: 1.5; color: #111; max-width: 800px;">

<div style="display: inline-block; border: 2px solid #111; padding: 8px 14px; font-family: 'Courier New', Courier, monospace; letter-spacing: 2px; margin-bottom: 20px; font-weight: bold;">
[ OLD SCHOOL SKATE ]${eraTag}
</div>

<p style="margin: 14px 0; font-size: 15px;">${intro}</p>

<hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">

<h2 style="font-size: 13px; letter-spacing: 1px; margin: 20px 0 10px; text-transform: uppercase; border-bottom: 2px solid #111; padding-bottom: 6px;">📋 KEY DETAILS</h2>
<ul style="margin: 0; padding-left: 20px; line-height: 1.8;">
${keyDetailsHtml}</ul>

<hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">

<h2 style="font-size: 13px; letter-spacing: 1px; margin: 20px 0 10px; text-transform: uppercase; border-bottom: 2px solid #111; padding-bottom: 6px;">🔍 CONDITION</h2>
<p style="margin: 10px 0;">${conditionSection}</p>
<p style="margin: 10px 0; font-style: italic;">All items are photographed in natural light to show true colors and condition. What you see is what you get.</p>

<hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">

<h2 style="font-size: 13px; letter-spacing: 1px; margin: 20px 0 10px; text-transform: uppercase; border-bottom: 2px solid #111; padding-bottom: 6px;">🏆 WHY BUY FROM US</h2>
<ul style="margin: 0; padding-left: 20px; line-height: 1.8;">
  <li>Specialized in <strong>vintage skateboard collectibles</strong> since years</li>
  <li>All items are <strong>100% authentic</strong> - we guarantee it</li>
  <li>Carefully packed to ensure <strong>safe delivery worldwide</strong></li>
  <li><strong>Fast shipping</strong> with tracking number provided</li>
  <li>Excellent feedback from collectors around the world</li>
</ul>

<hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">

<h2 style="font-size: 13px; letter-spacing: 1px; margin: 20px 0 10px; text-transform: uppercase; border-bottom: 2px solid #111; padding-bottom: 6px;">📦 SHIPPING & INFO</h2>
<p style="margin: 10px 0;">🌍 <strong>Ships from Milan, Italy</strong> to worldwide destinations.</p>
<p style="margin: 10px 0;">📬 Combined shipping available for multiple items—please message before purchase to save on shipping!</p>
<p style="margin: 10px 0;">⏱️ Items shipped within <strong>1-2 business days</strong> after payment.</p>
<p style="margin: 10px 0;">🛃 International buyers: import duties/taxes are not included and are the buyer's responsibility.</p>

<hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">

<p style="margin: 14px 0;">💬 <strong>Questions about ${brandName}?</strong> Feel free to message—I'm happy to help with any info, measurements, or additional photos!</p>

<p style="margin: 20px 0; font-size: 16px; text-align: center;"><strong>⭐ Thanks for looking! ⭐</strong></p>

<p style="margin: 10px 0; text-align: center; font-size: 12px; color: #666;">Check out my other vintage skateboard items!</p>

</div>`.trim();
};

// Key aspects that trigger title/description rebuild
const TITLE_TRIGGER_KEYS = ["Brand", "Model", "Size", "Width", "Era", "Decade", "Color", "Durometer", "Type", "Series", "Item Type"];

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
  const [aspectsMetadata, setAspectsMetadata] = useState({});
  const [condition, setCondition] = useState("NEW");
  const [categoryId, setCategoryId] = useState("");
  const [price, setPrice] = useState("");
  
  // Core Details (always visible)
  const [coreDetails, setCoreDetails] = useState({
    brand: "",
    model: "",
    size: "",
    color: "",
    era: ""
  });
  
  const [newAspectKey, setNewAspectKey] = useState("");
  const [newAspectValue, setNewAspectValue] = useState("");

  useEffect(() => {
    fetchDraft();
  }, [id]);

  // Auto-update title when core details or aspects change (if not manually edited)
  useEffect(() => {
    if (!titleManuallyEdited && draft?.item_type) {
      const hasCoreData = Object.values(coreDetails).some(v => cleanValue(v));
      if (hasCoreData) {
        const newTitle = buildEbayTitle(draft.item_type, coreDetails, aspects);
        if (newTitle && newTitle !== title) {
          setTitle(newTitle);
        }
      }
    }
  }, [coreDetails, aspects, draft?.item_type, titleManuallyEdited]);

  // Auto-update description when core details change (if not manually edited)
  useEffect(() => {
    if (!descriptionManuallyEdited && draft?.item_type) {
      const hasCoreData = Object.values(coreDetails).some(v => cleanValue(v));
      if (hasCoreData) {
        const newDescription = build90sDescription(draft.item_type, coreDetails, aspects, condition);
        if (newDescription && newDescription !== description) {
          setDescription(newDescription);
        }
      }
    }
  }, [coreDetails, aspects, condition, draft?.item_type, descriptionManuallyEdited]);

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
      setAspectsMetadata(data.aspects_metadata || {});
      setCondition(data.condition || "NEW");
      setCategoryId(data.category_id || "");
      setPrice(data.price?.toString() || "");
      
      // Set core details from response or extract from aspects
      setCoreDetails({
        brand: data.brand || data.aspects?.Brand || "",
        model: data.model || data.aspects?.Model || "",
        size: data.size || data.aspects?.Size || data.aspects?.Width || "",
        color: data.color || data.aspects?.Color || "",
        era: data.era || data.aspects?.Era || data.aspects?.Decade || ""
      });
    } catch (error) {
      toast.error("Failed to load draft");
      navigate("/");
    } finally {
      setLoading(false);
    }
  };

  const handleCoreDetailChange = (field, value) => {
    setCoreDetails(prev => ({ ...prev, [field]: value }));
    // Mark as manual edit in metadata
    const aspectKey = field === "era" ? "Era" : field.charAt(0).toUpperCase() + field.slice(1);
    setAspectsMetadata(prev => ({
      ...prev,
      [aspectKey]: { source: "manual", confidence: 1 }
    }));
    // Also sync to aspects
    setAspects(prev => ({
      ...prev,
      [aspectKey]: value
    }));
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
    if (draft?.item_type) {
      const newTitle = buildEbayTitle(draft.item_type, coreDetails, aspects);
      setTitle(newTitle);
      setTitleManuallyEdited(false);
      toast.success("Title regenerated");
    }
  };

  const handleRegenerateDescription = () => {
    if (draft?.item_type) {
      const newDescription = build90sDescription(draft.item_type, coreDetails, aspects, condition);
      setDescription(newDescription);
      setDescriptionManuallyEdited(false);
      toast.success("Description regenerated");
    }
  };

  const handleAutoFillAspects = async (force = false) => {
    setAutoFilling(true);
    try {
      toast.loading("Analyzing images...");
      const response = await api.post(`/drafts/${id}/autofill_aspects?force=${force}`);
      toast.dismiss();
      
      const { extracted_aspects, aspects_metadata: newMetadata, source } = response.data;
      
      // Update local state
      const newDraft = response.data.draft;
      setAspects(newDraft.aspects || {});
      setAspectsMetadata(newDraft.aspects_metadata || {});
      
      // Update core details
      setCoreDetails({
        brand: newDraft.brand || newDraft.aspects?.Brand || "",
        model: newDraft.model || newDraft.aspects?.Model || "",
        size: newDraft.size || newDraft.aspects?.Size || newDraft.aspects?.Width || "",
        color: newDraft.color || newDraft.aspects?.Color || "",
        era: newDraft.era || newDraft.aspects?.Era || newDraft.aspects?.Decade || ""
      });
      
      const count = Object.keys(extracted_aspects || {}).length;
      if (count > 0) {
        toast.success(`Auto-filled ${count} fields from ${source}`);
      } else {
        toast.info("No new aspects could be extracted");
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
    
    let titleToSave = title;
    
    // Validate title length
    if (title.length < 70) {
      toast.warning("Title is under 70 characters - consider adding more details");
    }
    
    if (title.length > 80) {
      titleToSave = title.substring(0, 77) + "...";
      setTitle(titleToSave);
      toast.warning("Title truncated to 80 characters");
    }
    
    try {
      await api.patch(`/drafts/${id}`, {
        title: titleToSave,
        title_manually_edited: titleManuallyEdited,
        description,
        description_manually_edited: descriptionManuallyEdited,
        aspects,
        aspects_metadata: aspectsMetadata,
        condition,
        category_id: categoryId,
        price: parseFloat(price) || 0,
        ...coreDetails
      });
      toast.success("Draft saved");
      await fetchDraft();
    } catch (error) {
      toast.error("Save failed");
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

  // Marketplace selection state
  const [selectedMarketplaces, setSelectedMarketplaces] = useState(["EBAY_US"]);
  const [showMarketplaceSelector, setShowMarketplaceSelector] = useState(false);
  const [publishResults, setPublishResults] = useState(null);

  const MARKETPLACES = [
    { id: "EBAY_US", name: "🇺🇸 USA", currency: "USD", defaultPrice: 25.00 },
    { id: "EBAY_DE", name: "🇩🇪 Germany", currency: "EUR", defaultPrice: 12.00 },
    { id: "EBAY_ES", name: "🇪🇸 Spain", currency: "EUR", defaultPrice: 12.00 },
    { id: "EBAY_AU", name: "🇦🇺 Australia", currency: "AUD", defaultPrice: 100.00 },
  ];

  const handlePublish = async () => {
    setPublishing(true);
    setPublishResults(null);
    try {
      const response = await api.post(`/drafts/${id}/publish-multi`, {
        marketplaces: selectedMarketplaces
      });
      
      const results = response.data;
      setPublishResults(results);
      
      // Count successes
      const successes = Object.values(results.marketplaces || {}).filter(r => r.success).length;
      const total = selectedMarketplaces.length;
      
      if (successes === total) {
        toast.success(`Published to ${successes} marketplace(s)!`);
      } else if (successes > 0) {
        toast.warning(`Published to ${successes}/${total} marketplaces`);
      } else {
        toast.error("Publish failed for all marketplaces");
      }
      
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

  const toggleMarketplace = (mpId) => {
    setSelectedMarketplaces(prev => 
      prev.includes(mpId) 
        ? prev.filter(id => id !== mpId)
        : [...prev, mpId]
    );
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
        aspects_metadata: aspectsMetadata,
        condition,
        category_id: categoryId,
        price: parseFloat(price) || 0,
        ...coreDetails
      });
      navigate(`/draft/${id}/preview`);
    } catch (error) {
      toast.error("Save failed before preview");
    } finally {
      setSaving(false);
    }
  };

  const handleRegenerate = async () => {
    setRegenerating(true);
    try {
      toast.loading("Generating content...");
      await api.post(`/drafts/${id}/generate`);
      toast.dismiss();
      toast.success("Content regenerated");
      await fetchDraft();
    } catch (error) {
      toast.dismiss();
      toast.error("Regeneration failed");
    } finally {
      setRegenerating(false);
    }
  };

  const handleAspectChange = (key, value) => {
    setAspects(prev => ({ ...prev, [key]: value }));
    setAspectsMetadata(prev => ({
      ...prev,
      [key]: { source: "manual", confidence: 1 }
    }));
    
    // Sync core fields: if changing Brand/Model/Size/Color/Era in aspects, update coreDetails too
    const coreMapping = {
      "Brand": "brand",
      "Model": "model", 
      "Size": "size",
      "Color": "color",
      "Era": "era",
      "Decade": "era",
      "Width": "size"
    };
    
    if (coreMapping[key]) {
      setCoreDetails(prev => ({ ...prev, [coreMapping[key]]: value }));
    }
  };

  const addAspect = () => {
    if (newAspectKey && newAspectValue) {
      setAspects(prev => ({ ...prev, [newAspectKey]: newAspectValue }));
      setAspectsMetadata(prev => ({
        ...prev,
        [newAspectKey]: { source: "manual", confidence: 1 }
      }));
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
    setAspectsMetadata(prev => {
      const newMeta = { ...prev };
      delete newMeta[key];
      return newMeta;
    });
  };

  const getSourceBadge = (key) => {
    const meta = aspectsMetadata[key];
    if (!meta) return null;
    
    const { source, confidence } = meta;
    if (source === "manual") return null;
    
    const confPercent = Math.round((confidence || 0.7) * 100);
    const bgColor = source === "photo" ? "bg-cyan-100 text-cyan-700 border-cyan-300" : "bg-amber-100 text-amber-700 border-amber-300";
    
    return (
      <Badge variant="outline" className={`text-[8px] ${bgColor} px-1 py-0 ml-1`}>
        auto ({source}) {confPercent}%
      </Badge>
    );
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

  // Core fields that are always shown first in Item Specifics
  const CORE_ASPECT_KEYS = ["Brand", "Size", "Era"];
  
  // Get all aspects for the item type (core + additional)
  const getAllAspectsForType = () => {
    switch (draft.item_type) {
      case "WHL":
        return ["Brand", "Size", "Durometer", "Era", "Quantity", "MPN"];
      case "TRK":
        return ["Brand", "Size", "Era", "Quantity", "MPN"];
      case "DCK":
        return ["Brand", "Series", "Size", "Width", "Length", "Era", "Artist"];
      case "APP":
        return ["Brand", "Department", "Size", "Era", "Measurements", "Style", "Fit"];
      default:
        return ["Brand", "Size", "Era"];
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
              <Button variant="outline" size="sm" onClick={handlePreview} disabled={saving}
                className="border-2 border-border shadow-hard-sm hover:translate-y-[1px] hover:shadow-none transition-all uppercase font-bold text-xs tracking-wider"
                data-testid="preview-btn">
                <Eye className="w-4 h-4 mr-2" />Preview
              </Button>
              <Button variant="outline" size="sm" onClick={handleRegenerate} disabled={regenerating || isPublished}
                className="border-2 border-border shadow-hard-sm hover:translate-y-[1px] hover:shadow-none transition-all uppercase font-bold text-xs tracking-wider"
                data-testid="regenerate-btn">
                <RefreshCw className={`w-4 h-4 mr-2 ${regenerating ? 'animate-spin' : ''}`} />Regenerate
              </Button>
              <Button variant="outline" size="sm" onClick={handleSave} disabled={saving || isPublished}
                className="border-2 border-border shadow-hard-sm hover:translate-y-[1px] hover:shadow-none transition-all uppercase font-bold text-xs tracking-wider"
                data-testid="save-btn">
                <Save className="w-4 h-4 mr-2" />Save
              </Button>
              {!isPublished && draft.status !== "READY" && (
                <Button variant="outline" size="sm" onClick={handleMarkReady} disabled={saving}
                  className="border-2 border-border shadow-hard-sm hover:translate-y-[1px] hover:shadow-none transition-all uppercase font-bold text-xs tracking-wider"
                  data-testid="mark-ready-btn">
                  <CheckCircle className="w-4 h-4 mr-2" />Mark Ready
                </Button>
              )}
              <Button size="sm" onClick={handlePublish} disabled={publishing || isPublished}
                className="bg-primary text-primary-foreground border-2 border-border shadow-hard-sm hover:translate-y-[1px] hover:shadow-none transition-all uppercase font-bold text-xs tracking-wider"
                data-testid="publish-btn">
                <Send className="w-4 h-4 mr-2" />{publishing ? "Publishing..." : "Publish"}
              </Button>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Left Column */}
          <div className="space-y-6">
            {/* Images */}
            <div className="bg-card border-2 border-border p-4 shadow-hard">
              <h3 className="font-heading font-bold uppercase tracking-tight mb-4 border-b-2 border-border pb-2">Images</h3>
              {draft.image_urls?.length > 0 ? (
                <div className="grid grid-cols-2 gap-2">
                  {draft.image_urls.map((url, i) => (
                    <img key={i}
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

            {/* Category & Price & Condition */}
            <div className="bg-card border-2 border-border p-4 shadow-hard space-y-4">
              <h3 className="font-heading font-bold uppercase tracking-tight border-b-2 border-border pb-2">Listing Details</h3>
              
              <div className="space-y-2">
                <Label className="text-xs font-bold uppercase tracking-widest">Category ID</Label>
                <Input value={categoryId} onChange={(e) => setCategoryId(e.target.value)} disabled={isPublished}
                  className="border-2 border-border font-mono" data-testid="edit-category-input" />
              </div>
              
              <div className="space-y-2">
                <Label className="text-xs font-bold uppercase tracking-widest">Price (USD)</Label>
                <Input type="number" step="0.01" value={price} onChange={(e) => setPrice(e.target.value)} disabled={isPublished}
                  className="border-2 border-border font-mono" data-testid="edit-price-input" />
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

            {/* Shipping Info */}
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
                    <Badge variant="outline" className="text-[9px] border-amber-400 text-amber-600">Manual</Badge>
                  )}
                </div>
                <div className="flex items-center gap-3">
                  <button onClick={handleRegenerateTitle} disabled={isPublished}
                    className="text-xs text-primary hover:underline flex items-center gap-1 disabled:opacity-50"
                    data-testid="regenerate-title-btn">
                    <Wand2 className="w-3 h-3" />Regenerate
                  </button>
                  <div className="flex items-center gap-1">
                    <span className={`font-mono text-xs font-bold ${
                      titleLength > 80 ? 'text-destructive' : titleLength >= 70 ? 'text-green-600' : 'text-muted-foreground'
                    }`}>{titleLength}</span>
                    <span className="font-mono text-xs text-muted-foreground">/80</span>
                    {titleLength >= 70 && titleLength <= 80 && <span className="text-[9px] text-green-600 font-bold ml-1">✓</span>}
                  </div>
                </div>
              </div>
              <Input value={title} onChange={handleTitleChange} disabled={isPublished}
                className={`border-2 font-mono ${titleLength > 80 ? 'border-destructive bg-red-50' : titleLength >= 70 ? 'border-green-500' : 'border-border'}`}
                placeholder="eBay listing title (max 80 chars)" data-testid="edit-title-input" />
              {titleLength > 80 && (
                <p className="text-destructive text-xs font-mono mt-1">⚠️ Title exceeds 80 characters - will be truncated on save</p>
              )}
              {titleLength < 70 && titleLength > 0 && (
                <p className="text-amber-600 text-xs font-mono mt-1">⚠️ Title under 70 characters - add more details or click Regenerate</p>
              )}
            </div>

            {/* Description */}
            <div className="bg-card border-2 border-border p-4 shadow-hard">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <Label className="text-xs font-bold uppercase tracking-widest">Description (90s Sticker Label)</Label>
                  {descriptionManuallyEdited && (
                    <Badge variant="outline" className="text-[9px] border-amber-400 text-amber-600">Manual</Badge>
                  )}
                </div>
                <button onClick={handleRegenerateDescription} disabled={isPublished}
                  className="text-xs text-primary hover:underline flex items-center gap-1 disabled:opacity-50"
                  data-testid="regenerate-description-btn">
                  <Wand2 className="w-3 h-3" />Regenerate
                </button>
              </div>
              <Textarea value={description} onChange={handleDescriptionChange} disabled={isPublished}
                rows={12} className="border-2 border-border font-mono text-sm"
                placeholder="Product description (HTML supported)" data-testid="edit-description-input" />
              <p className="text-xs text-muted-foreground mt-2 font-mono">
                💡 Description auto-updates when Core Details change (90s sticker label format).
              </p>
            </div>

            {/* Item Specifics - All fields for type */}
            <div className="bg-card border-2 border-border p-4 shadow-hard">
              <div className="flex items-center justify-between mb-4">
                <Label className="text-xs font-bold uppercase tracking-widest">
                  Item Specifics
                  <span className="text-muted-foreground font-normal ml-2">({draft.item_type})</span>
                </Label>
                {!isPublished && (draft.image_urls?.length > 0 || title) && (
                  <Button variant="outline" size="sm" onClick={() => handleAutoFillAspects(true)} disabled={autoFilling}
                    className="border-2 border-border shadow-hard-sm text-xs" data-testid="force-autofill-btn">
                    <Sparkles className="w-3 h-3 mr-1" />{autoFilling ? "..." : "Auto-fill All"}
                  </Button>
                )}
              </div>
              
              {/* Pre-defined fields for this item type */}
              <div className="space-y-2 mb-4">
                {getAllAspectsForType().map((key) => {
                  const value = aspects[key] || "";
                  const meta = aspectsMetadata[key];
                  const isAuto = meta && meta.source !== "manual";
                  const isCore = CORE_ASPECT_KEYS.includes(key);
                  
                  return (
                    <div key={key} className={`flex items-center gap-2 p-2 border-2 ${isCore ? 'border-primary bg-primary/5' : 'border-border'} ${isAuto ? 'bg-cyan-50' : ''}`}>
                      <div className="w-36 flex items-center gap-1">
                        <span className={`font-bold text-sm uppercase tracking-wider ${isCore ? 'text-primary' : ''}`}>
                          {key}
                        </span>
                        {isCore && <span className="text-[9px] text-primary">★</span>}
                        {isAuto && (
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
                        placeholder={key === "Size" ? (draft.item_type === "WHL" ? "e.g., 63mm" : draft.item_type === "DCK" ? "e.g., 10in" : "") : ""}
                        data-testid={`aspect-${key}`} 
                      />
                    </div>
                  );
                })}
                
                {/* Extra aspects not in predefined list */}
                {Object.entries(aspects)
                  .filter(([key]) => !getAllAspectsForType().includes(key))
                  .filter(([key]) => !["Type", "Model", "Color", "Item Type", "Material", "Notes"].includes(key))
                  .map(([key, value]) => {
                    const meta = aspectsMetadata[key];
                    const isAuto = meta && meta.source !== "manual";
                    return (
                      <div key={key} className={`flex items-center gap-2 p-2 border-2 border-border ${isAuto ? 'bg-cyan-50' : 'bg-muted'}`}>
                        <div className="w-36 flex items-center gap-1">
                          <span className="font-bold text-sm uppercase tracking-wider">{key}</span>
                          {isAuto && (
                            <Badge variant="outline" className="text-[8px] border-cyan-400 text-cyan-600 px-1 py-0">
                              auto
                            </Badge>
                          )}
                        </div>
                        <Input value={value} onChange={(e) => handleAspectChange(key, e.target.value)} disabled={isPublished}
                          className="flex-1 border-2 border-border font-mono text-sm h-8" data-testid={`aspect-${key}`} />
                        {!isPublished && (
                          <button onClick={() => removeAspect(key)}
                            className="w-8 h-8 flex items-center justify-center bg-destructive text-white border-2 border-border hover:bg-destructive/80">
                            <X className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    );
                  })}
              </div>
              
              {/* Add custom aspect */}
              {!isPublished && (
                <div className="flex gap-2 pt-2 border-t-2 border-border">
                  <Input value={newAspectKey} onChange={(e) => setNewAspectKey(e.target.value)}
                    placeholder="Custom field..." className="w-36 border-2 border-border font-mono text-sm" data-testid="new-aspect-key" />
                  <Input value={newAspectValue} onChange={(e) => setNewAspectValue(e.target.value)}
                    placeholder="Value" className="flex-1 border-2 border-border font-mono text-sm" data-testid="new-aspect-value" />
                  <Button variant="outline" size="sm" onClick={addAspect} disabled={!newAspectKey || !newAspectValue}
                    className="border-2 border-border shadow-hard-sm" data-testid="add-aspect-btn">
                    <Plus className="w-4 h-4" />
                  </Button>
                </div>
              )}
              
              <p className="text-xs text-muted-foreground mt-3 font-mono">
                ★ Core fields (Brand, Model, Size, Color, Era) update Title and Description automatically
              </p>
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
                {draft.listing_id && (
                  <a 
                    href={`https://www.sandbox.ebay.com/itm/${draft.listing_id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-2 mt-3 px-4 py-2 bg-green-600 text-white font-bold uppercase tracking-wider text-sm border-2 border-green-700 shadow-hard-sm hover:translate-y-[1px] hover:shadow-none transition-all"
                    data-testid="view-on-ebay-btn"
                  >
                    <ExternalLink className="w-4 h-4" />
                    View on eBay Sandbox
                  </a>
                )}
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
