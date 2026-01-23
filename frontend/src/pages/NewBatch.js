import { useState, useCallback, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import api from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Switch } from "../components/ui/switch";
import { Progress } from "../components/ui/progress";
import { toast } from "sonner";
import { 
  ArrowLeft, Upload, X, Sparkles, FolderOpen,
  Image as ImageIcon, Loader2, CheckCircle
} from "lucide-react";

export default function NewBatch() {
  const navigate = useNavigate();
  const [batchName, setBatchName] = useState("");
  const [files, setFiles] = useState([]);
  const [previews, setPreviews] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [manualGrouping, setManualGrouping] = useState(false);
  const [batchId, setBatchId] = useState(null);
  const [processing, setProcessing] = useState(false);
  const [jobId, setJobId] = useState(null);
  const [jobProgress, setJobProgress] = useState(0);
  const [jobMessage, setJobMessage] = useState("");
  const [step, setStep] = useState("upload"); // upload, grouping, generating, done

  // Poll job status
  useEffect(() => {
    if (!jobId) return;
    
    const interval = setInterval(async () => {
      try {
        const response = await api.get(`/jobs/${jobId}`);
        const job = response.data;
        setJobProgress(job.progress);
        setJobMessage(job.message || "");
        
        if (job.status === "COMPLETED") {
          clearInterval(interval);
          if (job.type === "auto_group") {
            setStep("generating");
            startGenerateDrafts();
          } else {
            setStep("done");
            toast.success("Drafts generati con successo!");
          }
        } else if (job.status === "ERROR") {
          clearInterval(interval);
          setProcessing(false);
          toast.error(job.error || "Errore durante l'elaborazione");
        }
      } catch (error) {
        console.error("Job poll error:", error);
      }
    }, 1000);
    
    return () => clearInterval(interval);
  }, [jobId]);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    const droppedFiles = Array.from(e.dataTransfer.files).filter(f => f.type.startsWith("image/"));
    addFiles(droppedFiles);
  }, []);

  const handleFileInput = (e) => {
    const selectedFiles = Array.from(e.target.files).filter(f => f.type.startsWith("image/"));
    addFiles(selectedFiles);
  };

  const addFiles = (newFiles) => {
    setFiles(prev => [...prev, ...newFiles]);
    
    // Create previews
    newFiles.forEach(file => {
      const reader = new FileReader();
      reader.onloadend = () => {
        setPreviews(prev => [...prev, { name: file.name, url: reader.result }]);
      };
      reader.readAsDataURL(file);
    });
  };

  const removeFile = (index) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
    setPreviews(prev => prev.filter((_, i) => i !== index));
  };

  const handleUploadAndProcess = async () => {
    if (files.length === 0) {
      toast.error("Seleziona almeno un'immagine");
      return;
    }

    setUploading(true);
    setUploadProgress(0);

    try {
      // 1. Create batch
      const batchRes = await api.post("/batches", { name: batchName || null });
      const newBatchId = batchRes.data.id;
      setBatchId(newBatchId);
      setUploadProgress(10);

      // 2. Upload images in chunks
      const chunkSize = 10;
      for (let i = 0; i < files.length; i += chunkSize) {
        const chunk = files.slice(i, i + chunkSize);
        const formData = new FormData();
        chunk.forEach(file => formData.append("files", file));
        
        await api.post(`/batches/${newBatchId}/upload`, formData, {
          headers: { "Content-Type": "multipart/form-data" }
        });
        
        const progress = 10 + Math.round(((i + chunk.length) / files.length) * 40);
        setUploadProgress(progress);
      }

      setUploadProgress(50);
      setUploading(false);

      if (manualGrouping) {
        // Go directly to batch review for manual grouping
        navigate(`/batch/${newBatchId}`);
      } else {
        // Start auto-grouping
        setProcessing(true);
        setStep("grouping");
        startAutoGroup(newBatchId);
      }

    } catch (error) {
      console.error("Upload error:", error);
      toast.error("Errore durante l'upload");
      setUploading(false);
    }
  };

  const startAutoGroup = async (bId) => {
    try {
      const response = await api.post(`/batches/${bId}/auto_group`);
      setJobId(response.data.job_id);
    } catch (error) {
      toast.error("Errore durante il raggruppamento automatico");
      setProcessing(false);
    }
  };

  const startGenerateDrafts = async () => {
    try {
      const response = await api.post(`/batches/${batchId}/generate_drafts`);
      setJobId(response.data.job_id);
    } catch (error) {
      toast.error("Errore durante la generazione dei draft");
      setProcessing(false);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="bg-card border-b-2 border-border">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center h-16">
            <Link to="/" className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors">
              <ArrowLeft className="w-4 h-4" />
              <span className="font-bold text-sm uppercase tracking-wider">Back</span>
            </Link>
            <h1 className="ml-6 font-heading font-bold text-xl uppercase tracking-tight">Batch Upload</h1>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Processing State */}
        {processing && (
          <div className="bg-card border-2 border-border p-8 shadow-hard mb-8">
            <div className="flex items-center gap-4 mb-6">
              <Loader2 className="w-8 h-8 animate-spin text-primary" />
              <div>
                <h2 className="font-heading font-bold text-xl uppercase">
                  {step === "grouping" ? "Auto-grouping..." : "Generating drafts..."}
                </h2>
                <p className="text-muted-foreground font-mono text-sm">{jobMessage}</p>
              </div>
            </div>
            <Progress value={jobProgress} className="h-3 border-2 border-border" />
            <p className="text-right font-mono text-sm mt-2">{jobProgress}%</p>
          </div>
        )}

        {/* Done State */}
        {step === "done" && (
          <div className="bg-green-50 border-2 border-green-400 p-8 mb-8">
            <div className="flex items-center gap-4">
              <CheckCircle className="w-12 h-12 text-green-600" />
              <div>
                <h2 className="font-heading font-bold text-xl uppercase text-green-800">
                  Batch completato!
                </h2>
                <p className="text-green-700 font-mono">
                  I draft sono stati generati. Vai alla revisione per controllarli.
                </p>
              </div>
            </div>
            <Button
              onClick={() => navigate(`/batch/${batchId}`)}
              className="mt-6 bg-green-600 text-white border-2 border-border shadow-hard hover:translate-y-[2px] hover:shadow-hard-sm transition-all uppercase font-bold tracking-wider"
              data-testid="go-to-review-btn"
            >
              Vai a Batch Review
            </Button>
          </div>
        )}

        {/* Upload UI */}
        {!processing && step === "upload" && (
          <>
            {/* Batch Name */}
            <div className="bg-card border-2 border-border p-6 shadow-hard mb-6">
              <Label className="text-xs font-bold uppercase tracking-widest mb-2 block">
                Nome Batch (opzionale)
              </Label>
              <Input
                value={batchName}
                onChange={(e) => setBatchName(e.target.value)}
                placeholder="es. Wheels Lot January 2025"
                className="border-2 border-border font-mono"
                data-testid="batch-name-input"
              />
            </div>

            {/* Drop Zone */}
            <div
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              className="border-2 border-dashed border-border bg-card p-12 text-center cursor-pointer hover:bg-muted/50 transition-colors mb-6"
              onClick={() => document.getElementById("batch-file-input").click()}
              data-testid="dropzone"
            >
              <Upload className="w-16 h-16 mx-auto mb-4 text-muted-foreground" />
              <h3 className="font-heading font-bold text-xl uppercase mb-2">
                Trascina le immagini qui
              </h3>
              <p className="text-muted-foreground font-mono text-sm mb-4">
                oppure clicca per selezionare (20-200 immagini)
              </p>
              <input
                id="batch-file-input"
                type="file"
                multiple
                accept="image/*"
                onChange={handleFileInput}
                className="hidden"
              />
            </div>

            {/* Preview Grid */}
            {previews.length > 0 && (
              <div className="bg-card border-2 border-border p-4 shadow-hard mb-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-heading font-bold uppercase">
                    {previews.length} immagini selezionate
                  </h3>
                  <button
                    onClick={() => { setFiles([]); setPreviews([]); }}
                    className="text-destructive text-xs font-bold uppercase hover:underline"
                  >
                    Rimuovi tutte
                  </button>
                </div>
                <div className="grid grid-cols-6 sm:grid-cols-8 md:grid-cols-10 gap-2 max-h-64 overflow-y-auto">
                  {previews.map((preview, idx) => (
                    <div key={idx} className="relative group">
                      <img
                        src={preview.url}
                        alt={preview.name}
                        className="w-full h-12 object-cover border border-border"
                      />
                      <button
                        onClick={(e) => { e.stopPropagation(); removeFile(idx); }}
                        className="absolute -top-1 -right-1 w-4 h-4 bg-destructive text-white rounded-full opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Options */}
            <div className="bg-card border-2 border-border p-6 shadow-hard mb-6">
              <div className="flex items-center justify-between">
                <div>
                  <Label className="text-sm font-bold">Raggruppamento manuale</Label>
                  <p className="text-xs text-muted-foreground font-mono">
                    Disattiva per usare l'auto-grouping con AI
                  </p>
                </div>
                <Switch
                  checked={manualGrouping}
                  onCheckedChange={setManualGrouping}
                  data-testid="manual-grouping-toggle"
                />
              </div>
            </div>

            {/* Upload Progress */}
            {uploading && (
              <div className="bg-card border-2 border-border p-6 shadow-hard mb-6">
                <div className="flex items-center gap-4 mb-4">
                  <Loader2 className="w-6 h-6 animate-spin" />
                  <span className="font-bold">Caricamento in corso...</span>
                </div>
                <Progress value={uploadProgress} className="h-3 border-2 border-border" />
                <p className="text-right font-mono text-sm mt-2">{uploadProgress}%</p>
              </div>
            )}

            {/* Action Button */}
            <Button
              onClick={handleUploadAndProcess}
              disabled={files.length === 0 || uploading}
              className="w-full bg-primary text-primary-foreground border-2 border-border shadow-hard hover:translate-y-[2px] hover:shadow-hard-sm disabled:opacity-50 transition-all uppercase font-bold tracking-wider py-6 text-lg"
              data-testid="upload-and-process-btn"
            >
              {manualGrouping ? (
                <>
                  <FolderOpen className="w-5 h-5 mr-2" />
                  Upload e raggruppa manualmente
                </>
              ) : (
                <>
                  <Sparkles className="w-5 h-5 mr-2" />
                  Upload e genera draft automaticamente
                </>
              )}
            </Button>

            {!manualGrouping && (
              <p className="text-center text-xs text-muted-foreground font-mono mt-4">
                L'AI analizzerà le immagini, le raggrupperà per oggetto e genererà titoli/descrizioni eBay-optimized
              </p>
            )}
          </>
        )}
      </main>
    </div>
  );
}
