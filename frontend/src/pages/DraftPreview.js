import { useState, useEffect } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import api from "../lib/api";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { Switch } from "../components/ui/switch";
import { Label } from "../components/ui/label";
import DOMPurify from "dompurify";
import { 
  ArrowLeft, Monitor, Smartphone, Code, Eye,
  ChevronLeft, ChevronRight, ImageIcon, Edit
} from "lucide-react";

// Configure DOMPurify allowlist
const ALLOWED_TAGS = ['p', 'br', 'ul', 'ol', 'li', 'strong', 'em', 'b', 'i', 'h2', 'h3', 'h4', 'blockquote', 'hr'];
const ALLOWED_ATTR = [];

const sanitizeHtml = (html) => {
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: ALLOWED_TAGS,
    ALLOWED_ATTR: ALLOWED_ATTR,
  });
};

const CONDITION_LABELS = {
  "NEW": "New",
  "LIKE_NEW": "Like New",
  "USED_EXCELLENT": "Used - Excellent",
  "USED_GOOD": "Used - Good",
  "USED_ACCEPTABLE": "Used - Acceptable",
  "FOR_PARTS_OR_NOT_WORKING": "For Parts or Not Working",
};

const ITEM_TYPE_LABELS = {
  "WHL": "Skateboard Wheels",
  "TRK": "Skateboard Trucks",
  "DCK": "Skateboard Deck",
};

export default function DraftPreview() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [preview, setPreview] = useState(null);
  const [currentImage, setCurrentImage] = useState(0);
  const [viewMode, setViewMode] = useState("desktop"); // desktop | mobile
  const [showHtmlSource, setShowHtmlSource] = useState(false);

  useEffect(() => {
    fetchPreview();
  }, [id]);

  const fetchPreview = async () => {
    try {
      const response = await api.get(`/drafts/${id}/preview`);
      setPreview(response.data);
    } catch (error) {
      navigate(`/draft/${id}`);
    } finally {
      setLoading(false);
    }
  };

  const nextImage = () => {
    if (preview?.images?.length > 0) {
      setCurrentImage((prev) => (prev + 1) % preview.images.length);
    }
  };

  const prevImage = () => {
    if (preview?.images?.length > 0) {
      setCurrentImage((prev) => (prev - 1 + preview.images.length) % preview.images.length);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="font-mono">Loading preview...</div>
      </div>
    );
  }

  if (!preview) return null;

  const hasImages = preview.images && preview.images.length > 0;

  // eBay-like preview content
  const PreviewContent = ({ isMobile }) => (
    <div className={`bg-white ${isMobile ? 'max-w-[375px] mx-auto' : 'w-full'}`}>
      {/* Header Bar */}
      <div className="bg-[#3665F3] text-white p-3 text-center">
        <span className="font-bold text-sm uppercase tracking-wider">eBay Preview</span>
        <span className="ml-2 text-xs opacity-75">(Not a real listing)</span>
      </div>

      <div className={`p-4 ${isMobile ? 'space-y-4' : 'grid grid-cols-2 gap-8 p-8'}`}>
        {/* Left Column - Images */}
        <div className={isMobile ? '' : ''}>
          {hasImages ? (
            <div className="relative border-2 border-gray-200">
              {/* Main Image */}
              <div className={`relative ${isMobile ? 'h-64' : 'h-96'} bg-gray-100`}>
                <img
                  src={preview.images[currentImage]}
                  alt={`Image ${currentImage + 1}`}
                  className="w-full h-full object-contain"
                  onError={(e) => {
                    e.target.src = 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200" viewBox="0 0 200 200"><rect fill="%23f3f4f6" width="200" height="200"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="%239ca3af" font-size="14">Image not found</text></svg>';
                  }}
                />
                
                {/* Navigation Arrows */}
                {preview.images.length > 1 && (
                  <>
                    <button
                      onClick={prevImage}
                      className="absolute left-2 top-1/2 -translate-y-1/2 w-10 h-10 bg-white/90 border border-gray-300 flex items-center justify-center hover:bg-white"
                      data-testid="prev-image-btn"
                    >
                      <ChevronLeft className="w-5 h-5" />
                    </button>
                    <button
                      onClick={nextImage}
                      className="absolute right-2 top-1/2 -translate-y-1/2 w-10 h-10 bg-white/90 border border-gray-300 flex items-center justify-center hover:bg-white"
                      data-testid="next-image-btn"
                    >
                      <ChevronRight className="w-5 h-5" />
                    </button>
                  </>
                )}
              </div>

              {/* Thumbnails */}
              {preview.images.length > 1 && (
                <div className="flex gap-2 p-2 overflow-x-auto bg-gray-50">
                  {preview.images.map((img, idx) => (
                    <button
                      key={idx}
                      onClick={() => setCurrentImage(idx)}
                      className={`w-16 h-16 flex-shrink-0 border-2 ${
                        idx === currentImage ? 'border-[#3665F3]' : 'border-gray-200'
                      }`}
                    >
                      <img
                        src={img}
                        alt={`Thumb ${idx + 1}`}
                        className="w-full h-full object-cover"
                        onError={(e) => {
                          e.target.style.display = 'none';
                        }}
                      />
                    </button>
                  ))}
                </div>
              )}

              {/* Image Counter */}
              <div className="absolute bottom-2 right-2 bg-black/70 text-white text-xs px-2 py-1">
                {currentImage + 1} / {preview.images.length}
              </div>
            </div>
          ) : (
            <div className="border-2 border-dashed border-gray-300 bg-gray-50 p-12 text-center">
              <ImageIcon className="w-16 h-16 mx-auto text-gray-400 mb-4" />
              <p className="text-gray-600 font-medium mb-4">No images yet</p>
              <Button
                onClick={() => navigate(`/draft/${id}`)}
                variant="outline"
                className="border-2 border-border"
                data-testid="go-back-upload-btn"
              >
                <ArrowLeft className="w-4 h-4 mr-2" />
                Go back and upload images
              </Button>
            </div>
          )}
        </div>

        {/* Right Column - Details */}
        <div className="space-y-4">
          {/* Title */}
          <h1 className={`font-bold text-gray-900 ${isMobile ? 'text-lg' : 'text-2xl'}`}>
            {preview.title}
          </h1>

          {/* Price */}
          <div className="flex items-baseline gap-2">
            <span className={`font-bold text-[#3665F3] ${isMobile ? 'text-2xl' : 'text-3xl'}`}>
              US ${preview.price?.toFixed(2) || '0.00'}
            </span>
          </div>

          {/* Condition */}
          <div className="flex items-center gap-2">
            <span className="text-gray-600">Condition:</span>
            <span className="font-medium">{CONDITION_LABELS[preview.condition] || preview.condition}</span>
          </div>

          {/* Category & SKU */}
          <div className="text-sm text-gray-500 space-y-1">
            <p>Category ID: {preview.categoryId || 'Not set'}</p>
            <p>SKU: {preview.sku}</p>
            <p>Type: {ITEM_TYPE_LABELS[preview.itemType] || preview.itemType}</p>
          </div>

          {/* Item Specifics */}
          {preview.aspects && Object.keys(preview.aspects).length > 0 && (
            <div className="border-t border-gray-200 pt-4">
              <h3 className="font-bold text-gray-900 mb-3">Item specifics</h3>
              <table className="w-full text-sm">
                <tbody>
                  {Object.entries(preview.aspects).map(([key, value]) => (
                    <tr key={key} className="border-b border-gray-100">
                      <td className="py-2 pr-4 text-gray-600 font-medium w-1/3">{key}</td>
                      <td className="py-2 text-gray-900">{value}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Description Section */}
      <div className="border-t border-gray-200 p-4 md:p-8">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-bold text-xl text-gray-900">Item description</h2>
          <div className="flex items-center gap-2">
            <Label htmlFor="html-toggle" className="text-sm text-gray-600">
              {showHtmlSource ? 'HTML Source' : 'Rendered'}
            </Label>
            <Switch
              id="html-toggle"
              checked={showHtmlSource}
              onCheckedChange={setShowHtmlSource}
              data-testid="html-toggle"
            />
          </div>
        </div>

        {showHtmlSource ? (
          <div className="bg-gray-900 text-gray-100 p-4 font-mono text-sm overflow-x-auto whitespace-pre-wrap border-2 border-gray-700">
            {preview.descriptionRaw || '<no description>'}
          </div>
        ) : (
          <div 
            className="prose prose-sm max-w-none text-gray-700"
            dangerouslySetInnerHTML={{ 
              __html: sanitizeHtml(preview.descriptionHtml || '<p>No description</p>') 
            }}
          />
        )}
      </div>

      {/* Footer */}
      <div className="bg-gray-100 p-4 text-center text-sm text-gray-500">
        This is a preview only. The listing has not been published to eBay.
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="bg-card border-b-2 border-border sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-4">
              <Link 
                to={`/draft/${id}`} 
                className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors"
              >
                <ArrowLeft className="w-4 h-4" />
                <span className="font-bold text-sm uppercase tracking-wider">Back to Editor</span>
              </Link>
              <span className="font-mono text-sm">{preview.sku}</span>
              <Badge className={`uppercase text-[10px] font-bold border-2 border-border ${
                preview.status === 'PUBLISHED' ? 'bg-green-500 text-white' : 'bg-gray-200 text-black'
              }`}>
                {preview.status}
              </Badge>
            </div>
            
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => navigate(`/draft/${id}`)}
                className="border-2 border-border shadow-hard-sm hover:translate-y-[1px] hover:shadow-none transition-all uppercase font-bold text-xs tracking-wider"
                data-testid="edit-draft-btn"
              >
                <Edit className="w-4 h-4 mr-2" />
                Edit Draft
              </Button>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* View Mode Tabs */}
        <Tabs value={viewMode} onValueChange={setViewMode} className="w-full">
          <div className="flex items-center justify-between mb-6">
            <h1 className="font-heading font-bold text-2xl uppercase tracking-tight">
              eBay Listing Preview
            </h1>
            <TabsList className="border-2 border-border bg-white">
              <TabsTrigger 
                value="desktop" 
                className="data-[state=active]:bg-primary data-[state=active]:text-white uppercase font-bold text-xs tracking-wider"
                data-testid="desktop-tab"
              >
                <Monitor className="w-4 h-4 mr-2" />
                Desktop
              </TabsTrigger>
              <TabsTrigger 
                value="mobile"
                className="data-[state=active]:bg-primary data-[state=active]:text-white uppercase font-bold text-xs tracking-wider"
                data-testid="mobile-tab"
              >
                <Smartphone className="w-4 h-4 mr-2" />
                Mobile
              </TabsTrigger>
            </TabsList>
          </div>

          <TabsContent value="desktop" className="mt-0">
            <div className="border-2 border-border shadow-hard bg-white">
              <PreviewContent isMobile={false} />
            </div>
          </TabsContent>

          <TabsContent value="mobile" className="mt-0">
            <div className="flex justify-center">
              <div className="border-2 border-border shadow-hard bg-white w-[400px] rounded-[20px] overflow-hidden">
                {/* Phone Frame */}
                <div className="bg-black p-2">
                  <div className="w-20 h-1 bg-gray-700 mx-auto rounded-full" />
                </div>
                <PreviewContent isMobile={true} />
                {/* Home Indicator */}
                <div className="bg-black p-3">
                  <div className="w-32 h-1 bg-gray-700 mx-auto rounded-full" />
                </div>
              </div>
            </div>
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}
