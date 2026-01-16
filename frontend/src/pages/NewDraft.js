import { useState, useCallback } from "react";
import { useNavigate, Link } from "react-router-dom";
import api from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { toast } from "sonner";
import { 
  ArrowLeft, ArrowRight, Upload, X, Check,
  Circle, Truck, ImageIcon, DollarSign, Sparkles
} from "lucide-react";

const ITEM_TYPES = [
  { code: "WHL", label: "Wheels", icon: "🛞", desc: "Skateboard wheels of all sizes" },
  { code: "TRK", label: "Trucks", icon: "🔧", desc: "Trucks and hardware" },
  { code: "DCK", label: "Decks", icon: "🛹", desc: "Skateboard decks" },
  { code: "APP", label: "Apparel", icon: "👕", desc: "T-shirts, hoodies, caps, pants" },
  { code: "MISC", label: "Misc", icon: "📦", desc: "Other skateboard items" },
];

const STEPS = [
  { id: 1, label: "Type", icon: Circle },
  { id: 2, label: "Photos", icon: ImageIcon },
  { id: 3, label: "Details", icon: DollarSign },
  { id: 4, label: "Generate", icon: Sparkles },
];

export default function NewDraft() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  
  // Form state
  const [itemType, setItemType] = useState("");
  const [images, setImages] = useState([]);
  const [imageUrls, setImageUrls] = useState([]);
  const [categoryId, setCategoryId] = useState("");
  const [price, setPrice] = useState("");

  const handleFileChange = (e) => {
    const files = Array.from(e.target.files);
    setImages(prev => [...prev, ...files]);
    
    // Create preview URLs
    files.forEach(file => {
      const reader = new FileReader();
      reader.onloadend = () => {
        setImageUrls(prev => [...prev, reader.result]);
      };
      reader.readAsDataURL(file);
    });
  };

  const removeImage = (index) => {
    setImages(prev => prev.filter((_, i) => i !== index));
    setImageUrls(prev => prev.filter((_, i) => i !== index));
  };

  const uploadImages = async () => {
    if (images.length === 0) return [];
    
    const formData = new FormData();
    images.forEach(file => formData.append("files", file));
    
    try {
      const response = await api.post("/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" }
      });
      return response.data.urls;
    } catch (error) {
      throw new Error("Failed to upload images");
    }
  };

  const handleCreateDraft = async () => {
    setLoading(true);
    
    try {
      // Upload images first
      const uploadedUrls = await uploadImages();
      
      // Create draft with condition = NEW (default)
      const response = await api.post("/drafts", {
        item_type: itemType,
        category_id: categoryId,
        price: parseFloat(price),
        image_urls: uploadedUrls,
        condition: "NEW"  // Default to NEW
      });
      
      const draftId = response.data.id;
      
      // Generate content
      toast.loading("Generating content with AI...");
      await api.post(`/drafts/${draftId}/generate`);
      toast.dismiss();
      
      toast.success("Draft created successfully!");
      navigate(`/draft/${draftId}`);
      
    } catch (error) {
      toast.dismiss();
      toast.error(error.response?.data?.detail || error.message || "Failed to create draft");
    } finally {
      setLoading(false);
    }
  };

  const canProceed = () => {
    switch (step) {
      case 1: return !!itemType;
      case 2: return images.length > 0;
      case 3: return !!categoryId && !!price && parseFloat(price) > 0;
      case 4: return true;
      default: return false;
    }
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="bg-card border-b-2 border-border">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center h-16">
            <Link to="/" className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors">
              <ArrowLeft className="w-4 h-4" />
              <span className="font-bold text-sm uppercase tracking-wider">Back</span>
            </Link>
            <h1 className="ml-6 font-heading font-bold text-xl uppercase tracking-tight">New Draft</h1>
          </div>
        </div>
      </header>

      {/* Progress Steps */}
      <div className="bg-card border-b-2 border-border">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            {STEPS.map((s, index) => {
              const Icon = s.icon;
              const isActive = step === s.id;
              const isComplete = step > s.id;
              
              return (
                <div key={s.id} className="flex items-center">
                  <div className={`flex items-center gap-2 ${isActive ? 'text-primary' : isComplete ? 'text-green-600' : 'text-muted-foreground'}`}>
                    <div className={`w-8 h-8 flex items-center justify-center border-2 ${isActive ? 'border-primary bg-primary text-white' : isComplete ? 'border-green-600 bg-green-600 text-white' : 'border-border'}`}>
                      {isComplete ? <Check className="w-4 h-4" /> : <Icon className="w-4 h-4" />}
                    </div>
                    <span className="hidden sm:block font-bold text-xs uppercase tracking-wider">{s.label}</span>
                  </div>
                  {index < STEPS.length - 1 && (
                    <div className={`w-8 sm:w-16 h-0.5 mx-2 ${isComplete ? 'bg-green-600' : 'bg-border'}`} />
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <main className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Step 1: Select Type */}
        {step === 1 && (
          <div className="space-y-6">
            <div>
              <h2 className="font-heading font-bold text-2xl uppercase tracking-tight mb-2">Select Item Type</h2>
              <p className="text-muted-foreground font-mono text-sm">Choose the category for your vintage skateboard item</p>
            </div>
            
            <div className="grid gap-4">
              {ITEM_TYPES.map((type) => (
                <button
                  key={type.code}
                  onClick={() => setItemType(type.code)}
                  className={`flex items-center gap-4 p-6 border-2 text-left transition-all ${
                    itemType === type.code 
                      ? 'border-primary bg-primary/5 shadow-hard-primary' 
                      : 'border-border bg-card shadow-hard hover:translate-y-[2px] hover:shadow-hard-sm'
                  }`}
                  data-testid={`type-${type.code}`}
                >
                  <span className="text-4xl">{type.icon}</span>
                  <div>
                    <h3 className="font-heading font-bold text-xl uppercase">{type.label}</h3>
                    <p className="text-muted-foreground font-mono text-sm">{type.desc}</p>
                  </div>
                  {itemType === type.code && (
                    <Check className="w-6 h-6 text-primary ml-auto" />
                  )}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Step 2: Upload Photos */}
        {step === 2 && (
          <div className="space-y-6">
            <div>
              <h2 className="font-heading font-bold text-2xl uppercase tracking-tight mb-2">Upload Photos</h2>
              <p className="text-muted-foreground font-mono text-sm">Add photos of your item (multiple allowed)</p>
            </div>
            
            <div 
              className="border-2 border-dashed border-border p-8 text-center bg-card hover:bg-muted/50 transition-colors cursor-pointer"
              onClick={() => document.getElementById('file-input').click()}
            >
              <Upload className="w-12 h-12 mx-auto mb-4 text-muted-foreground" />
              <p className="font-bold uppercase tracking-wider mb-2">Click to upload</p>
              <p className="text-sm text-muted-foreground font-mono">or drag and drop</p>
              <input
                id="file-input"
                type="file"
                multiple
                accept="image/*"
                onChange={handleFileChange}
                className="hidden"
                data-testid="file-input"
              />
            </div>
            
            {imageUrls.length > 0 && (
              <div className="grid grid-cols-3 gap-4">
                {imageUrls.map((url, index) => (
                  <div key={index} className="relative border-2 border-border bg-card shadow-hard">
                    <img src={url} alt={`Preview ${index + 1}`} className="w-full h-32 object-cover" />
                    <button
                      onClick={() => removeImage(index)}
                      className="absolute top-2 right-2 w-6 h-6 bg-destructive text-white flex items-center justify-center border-2 border-border"
                      data-testid={`remove-image-${index}`}
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Step 3: Category & Price */}
        {step === 3 && (
          <div className="space-y-6">
            <div>
              <h2 className="font-heading font-bold text-2xl uppercase tracking-tight mb-2">Item Details</h2>
              <p className="text-muted-foreground font-mono text-sm">Enter the eBay category ID and price</p>
            </div>
            
            <div className="bg-card border-2 border-border p-6 shadow-hard space-y-6">
              <div className="space-y-2">
                <Label htmlFor="categoryId" className="text-xs font-bold uppercase tracking-widest">
                  eBay Category ID
                </Label>
                <Input
                  id="categoryId"
                  value={categoryId}
                  onChange={(e) => setCategoryId(e.target.value)}
                  placeholder="e.g., 16265"
                  className="border-2 border-border font-mono"
                  data-testid="category-input"
                />
                <p className="text-xs text-muted-foreground font-mono">
                  Find category IDs at eBay Seller Hub or use: 16265 (Skateboard Wheels), 16264 (Trucks), 16263 (Decks)
                </p>
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="price" className="text-xs font-bold uppercase tracking-widest">
                  Price (USD)
                </Label>
                <div className="relative">
                  <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                  <Input
                    id="price"
                    type="number"
                    step="0.01"
                    min="0"
                    value={price}
                    onChange={(e) => setPrice(e.target.value)}
                    placeholder="0.00"
                    className="pl-10 border-2 border-border font-mono"
                    data-testid="price-input"
                  />
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Step 4: Review & Generate */}
        {step === 4 && (
          <div className="space-y-6">
            <div>
              <h2 className="font-heading font-bold text-2xl uppercase tracking-tight mb-2">Review & Generate</h2>
              <p className="text-muted-foreground font-mono text-sm">Confirm details and generate AI content</p>
            </div>
            
            <div className="bg-card border-2 border-border p-6 shadow-hard space-y-4">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Type</span>
                  <p className="font-mono">{ITEM_TYPES.find(t => t.code === itemType)?.label}</p>
                </div>
                <div>
                  <span className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Photos</span>
                  <p className="font-mono">{images.length} images</p>
                </div>
                <div>
                  <span className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Category ID</span>
                  <p className="font-mono">{categoryId}</p>
                </div>
                <div>
                  <span className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Price</span>
                  <p className="font-mono">${parseFloat(price).toFixed(2)}</p>
                </div>
              </div>
              
              {imageUrls.length > 0 && (
                <div className="border-t-2 border-border pt-4">
                  <span className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Preview</span>
                  <div className="flex gap-2 mt-2 overflow-x-auto">
                    {imageUrls.slice(0, 4).map((url, i) => (
                      <img key={i} src={url} alt="" className="w-16 h-16 object-cover border-2 border-border" />
                    ))}
                    {imageUrls.length > 4 && (
                      <div className="w-16 h-16 bg-muted border-2 border-border flex items-center justify-center font-mono text-sm">
                        +{imageUrls.length - 4}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
            
            <div className="bg-amber-50 border-2 border-amber-400 p-4">
              <p className="text-sm font-mono">
                <Sparkles className="w-4 h-4 inline mr-2 text-amber-600" />
                Clicking "Generate Draft" will upload your images and use AI to create an optimized eBay listing title, description, and item specifics.
              </p>
            </div>
          </div>
        )}

        {/* Navigation */}
        <div className="flex justify-between mt-8 pt-6 border-t-2 border-border">
          <Button
            variant="outline"
            onClick={() => step > 1 ? setStep(step - 1) : navigate("/")}
            className="border-2 border-border shadow-hard hover:translate-y-[2px] hover:shadow-hard-sm transition-all uppercase font-bold tracking-wider"
            data-testid="back-btn"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            {step > 1 ? "Back" : "Cancel"}
          </Button>
          
          {step < 4 ? (
            <Button
              onClick={() => setStep(step + 1)}
              disabled={!canProceed()}
              className="bg-primary text-primary-foreground border-2 border-border shadow-hard hover:translate-y-[2px] hover:shadow-hard-sm disabled:opacity-50 disabled:cursor-not-allowed transition-all uppercase font-bold tracking-wider"
              data-testid="next-btn"
            >
              Next
              <ArrowRight className="w-4 h-4 ml-2" />
            </Button>
          ) : (
            <Button
              onClick={handleCreateDraft}
              disabled={loading}
              className="bg-primary text-primary-foreground border-2 border-border shadow-hard hover:translate-y-[2px] hover:shadow-hard-sm disabled:opacity-50 transition-all uppercase font-bold tracking-wider"
              data-testid="generate-btn"
            >
              {loading ? (
                <>Generating...</>
              ) : (
                <>
                  <Sparkles className="w-4 h-4 mr-2" />
                  Generate Draft
                </>
              )}
            </Button>
          )}
        </div>
      </main>
    </div>
  );
}
