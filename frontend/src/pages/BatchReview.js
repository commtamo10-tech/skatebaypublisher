import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import api from "../lib/api";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Progress } from "../components/ui/progress";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
import { toast } from "sonner";
import { 
  ArrowLeft, Sparkles, RefreshCw, Trash2, Edit,
  Split, Merge, GripVertical, Eye, Loader2,
  CheckCircle, AlertTriangle, Image as ImageIcon
} from "lucide-react";

const ITEM_TYPES = {
  WHL: { label: "Wheels", color: "bg-blue-500" },
  TRK: { label: "Trucks", color: "bg-orange-500" },
  DCK: { label: "Decks", color: "bg-green-500" },
  APP: { label: "Apparel", color: "bg-purple-500" },
  MISC: { label: "Misc", color: "bg-gray-500" },
};

export default function BatchReview() {
  const { batchId } = useParams();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [batch, setBatch] = useState(null);
  const [groups, setGroups] = useState([]);
  const [images, setImages] = useState([]);
  const [drafts, setDrafts] = useState([]);
  const [selectedGroups, setSelectedGroups] = useState([]);
  const [splitMode, setSplitMode] = useState(null); // group_id when in split mode
  const [selectedImages, setSelectedImages] = useState([]);
  const [processing, setProcessing] = useState(false);
  const [jobId, setJobId] = useState(null);
  const [jobProgress, setJobProgress] = useState(0);
  const [jobMessage, setJobMessage] = useState("");

  useEffect(() => {
    fetchData();
  }, [batchId]);

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
          setProcessing(false);
          setJobId(null);
          toast.success("Operazione completata!");
          fetchData();
        } else if (job.status === "ERROR") {
          clearInterval(interval);
          setProcessing(false);
          setJobId(null);
          toast.error(job.error || "Errore durante l'elaborazione");
        }
      } catch (error) {
        console.error("Job poll error:", error);
      }
    }, 1000);
    
    return () => clearInterval(interval);
  }, [jobId]);

  const fetchData = async () => {
    try {
      const [batchRes, groupsRes, imagesRes, draftsRes] = await Promise.all([
        api.get(`/batches/${batchId}`),
        api.get(`/batches/${batchId}/groups`),
        api.get(`/batches/${batchId}/images`),
        api.get(`/drafts?batch_id=${batchId}`)
      ]);
      
      setBatch(batchRes.data);
      setGroups(groupsRes.data.groups || []);
      setImages(imagesRes.data.images || []);
      
      // Map drafts by group_id
      const draftsByGroup = {};
      (draftsRes.data || []).forEach(d => {
        if (d.group_id) draftsByGroup[d.group_id] = d;
      });
      setDrafts(draftsByGroup);
      
    } catch (error) {
      toast.error("Errore nel caricamento");
      navigate("/");
    } finally {
      setLoading(false);
    }
  };

  const getGroupImages = (groupId) => {
    const group = groups.find(g => g.id === groupId);
    if (!group) return [];
    return images.filter(img => group.image_ids.includes(img.id));
  };

  const getUnassignedImages = () => {
    const assignedIds = groups.flatMap(g => g.image_ids);
    return images.filter(img => !assignedIds.includes(img.id));
  };

  const handleAutoGroup = async () => {
    setProcessing(true);
    try {
      const response = await api.post(`/batches/${batchId}/auto_group`);
      setJobId(response.data.job_id);
    } catch (error) {
      toast.error("Errore");
      setProcessing(false);
    }
  };

  const handleGenerateDrafts = async () => {
    setProcessing(true);
    try {
      const response = await api.post(`/batches/${batchId}/generate_drafts`);
      setJobId(response.data.job_id);
    } catch (error) {
      toast.error("Errore");
      setProcessing(false);
    }
  };

  const handleChangeType = async (groupId, newType) => {
    try {
      await api.patch(`/batches/${batchId}/groups/${groupId}`, { suggested_type: newType });
      setGroups(prev => prev.map(g => g.id === groupId ? { ...g, suggested_type: newType } : g));
      toast.success("Tipo aggiornato");
    } catch (error) {
      toast.error("Errore");
    }
  };

  const handleDeleteGroup = async (groupId) => {
    if (!window.confirm("Eliminare questo gruppo?")) return;
    try {
      await api.delete(`/batches/${batchId}/groups/${groupId}`);
      fetchData();
      toast.success("Gruppo eliminato");
    } catch (error) {
      toast.error("Errore");
    }
  };

  const handleMergeGroups = async () => {
    if (selectedGroups.length < 2) {
      toast.error("Seleziona almeno 2 gruppi da unire");
      return;
    }
    try {
      await api.post(`/batches/${batchId}/merge_groups`, { group_ids: selectedGroups });
      setSelectedGroups([]);
      fetchData();
      toast.success("Gruppi uniti");
    } catch (error) {
      toast.error("Errore");
    }
  };

  const handleSplit = async (groupId) => {
    if (selectedImages.length === 0) {
      toast.error("Seleziona le immagini da spostare");
      return;
    }
    try {
      await api.post(`/batches/${batchId}/groups/${groupId}/split`, selectedImages);
      setSplitMode(null);
      setSelectedImages([]);
      fetchData();
      toast.success("Gruppo diviso");
    } catch (error) {
      toast.error("Errore");
    }
  };

  const toggleGroupSelection = (groupId) => {
    setSelectedGroups(prev => 
      prev.includes(groupId) ? prev.filter(id => id !== groupId) : [...prev, groupId]
    );
  };

  const toggleImageSelection = (imageId) => {
    setSelectedImages(prev => 
      prev.includes(imageId) ? prev.filter(id => id !== imageId) : [...prev, imageId]
    );
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="font-mono">Loading...</div>
      </div>
    );
  }

  if (!batch) return null;

  const unassignedImages = getUnassignedImages();
  const groupsWithoutDrafts = groups.filter(g => !g.draft_id);

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="bg-card border-b-2 border-border sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-4">
              <Link to="/" className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors">
                <ArrowLeft className="w-4 h-4" />
                <span className="font-bold text-sm uppercase tracking-wider">Back</span>
              </Link>
              <h1 className="font-heading font-bold text-xl uppercase tracking-tight">
                Batch Review
              </h1>
              <Badge variant="outline" className="border-2 border-border font-mono">
                {batch.name}
              </Badge>
            </div>
            
            <div className="flex items-center gap-2">
              {selectedGroups.length >= 2 && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleMergeGroups}
                  className="border-2 border-border shadow-hard-sm uppercase font-bold text-xs"
                  data-testid="merge-btn"
                >
                  <Merge className="w-4 h-4 mr-2" />
                  Merge ({selectedGroups.length})
                </Button>
              )}
              {groups.length > 0 && groupsWithoutDrafts.length > 0 && (
                <Button
                  onClick={handleGenerateDrafts}
                  disabled={processing}
                  className="bg-primary text-primary-foreground border-2 border-border shadow-hard-sm uppercase font-bold text-xs"
                  data-testid="generate-drafts-btn"
                >
                  <Sparkles className="w-4 h-4 mr-2" />
                  Generate Drafts ({groupsWithoutDrafts.length})
                </Button>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Processing Overlay */}
      {processing && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-card border-2 border-border p-8 shadow-hard max-w-md w-full mx-4">
            <div className="flex items-center gap-4 mb-6">
              <Loader2 className="w-8 h-8 animate-spin text-primary" />
              <div>
                <h2 className="font-heading font-bold text-xl uppercase">Elaborazione...</h2>
                <p className="text-muted-foreground font-mono text-sm">{jobMessage}</p>
              </div>
            </div>
            <Progress value={jobProgress} className="h-3 border-2 border-border" />
            <p className="text-right font-mono text-sm mt-2">{jobProgress}%</p>
          </div>
        </div>
      )}

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Stats */}
        <div className="grid grid-cols-4 gap-4 mb-8">
          <div className="bg-card border-2 border-border p-4 shadow-hard">
            <p className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Immagini</p>
            <p className="text-2xl font-heading font-black">{images.length}</p>
          </div>
          <div className="bg-card border-2 border-border p-4 shadow-hard">
            <p className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Gruppi</p>
            <p className="text-2xl font-heading font-black">{groups.length}</p>
          </div>
          <div className="bg-card border-2 border-border p-4 shadow-hard">
            <p className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Draft Creati</p>
            <p className="text-2xl font-heading font-black">{Object.keys(drafts).length}</p>
          </div>
          <div className="bg-card border-2 border-border p-4 shadow-hard">
            <p className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Non Assegnate</p>
            <p className="text-2xl font-heading font-black">{unassignedImages.length}</p>
          </div>
        </div>

        {/* No groups message */}
        {groups.length === 0 && (
          <div className="bg-card border-2 border-border p-12 shadow-hard text-center mb-8">
            <ImageIcon className="w-16 h-16 mx-auto text-muted-foreground mb-4" />
            <h3 className="font-heading font-bold text-xl uppercase mb-2">Nessun gruppo</h3>
            <p className="text-muted-foreground font-mono mb-6">
              {images.length > 0 
                ? "Avvia l'auto-grouping per creare gruppi automaticamente"
                : "Carica delle immagini prima"}
            </p>
            {images.length > 0 && (
              <Button
                onClick={handleAutoGroup}
                disabled={processing}
                className="bg-primary text-primary-foreground border-2 border-border shadow-hard uppercase font-bold"
                data-testid="auto-group-btn"
              >
                <Sparkles className="w-4 h-4 mr-2" />
                Auto-Group Images
              </Button>
            )}
          </div>
        )}

        {/* Groups Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {groups.map((group) => {
            const groupImages = getGroupImages(group.id);
            const draft = drafts[group.id];
            const typeInfo = ITEM_TYPES[group.suggested_type] || ITEM_TYPES.MISC;
            const isSelected = selectedGroups.includes(group.id);
            const isSplitting = splitMode === group.id;

            return (
              <div
                key={group.id}
                className={`bg-card border-2 shadow-hard transition-all ${
                  isSelected ? 'border-primary ring-2 ring-primary' : 'border-border'
                }`}
                data-testid={`group-${group.id}`}
              >
                {/* Group Header */}
                <div className="p-4 border-b-2 border-border flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => toggleGroupSelection(group.id)}
                      className={`w-5 h-5 border-2 border-border flex items-center justify-center ${isSelected ? 'bg-primary text-white' : ''}`}
                    >
                      {isSelected && <CheckCircle className="w-3 h-3" />}
                    </button>
                    <Select
                      value={group.suggested_type}
                      onValueChange={(val) => handleChangeType(group.id, val)}
                    >
                      <SelectTrigger className="w-28 h-8 border-2 border-border text-xs">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {Object.entries(ITEM_TYPES).map(([code, info]) => (
                          <SelectItem key={code} value={code}>{info.label}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <Badge className={`${typeInfo.color} text-white text-[10px]`}>
                      {Math.round(group.confidence * 100)}%
                    </Badge>
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => {
                        if (isSplitting) {
                          setSplitMode(null);
                          setSelectedImages([]);
                        } else {
                          setSplitMode(group.id);
                          setSelectedImages([]);
                        }
                      }}
                      className={`p-1 hover:bg-muted ${isSplitting ? 'bg-amber-100 text-amber-700' : ''}`}
                      title="Split"
                    >
                      <Split className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => handleDeleteGroup(group.id)}
                      className="p-1 hover:bg-destructive/10 text-destructive"
                      title="Delete"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                {/* Images Grid */}
                <div className="p-3 grid grid-cols-4 gap-1">
                  {groupImages.slice(0, 8).map((img) => {
                    const imgSelected = selectedImages.includes(img.id);
                    return (
                      <div
                        key={img.id}
                        onClick={() => isSplitting && toggleImageSelection(img.id)}
                        className={`relative aspect-square cursor-pointer ${
                          isSplitting ? 'cursor-pointer' : ''
                        } ${imgSelected ? 'ring-2 ring-primary' : ''}`}
                      >
                        <img
                          src={img.url.startsWith('http') ? img.url : `${process.env.REACT_APP_BACKEND_URL}${img.url}`}
                          alt=""
                          className="w-full h-full object-cover border border-border"
                        />
                        {imgSelected && (
                          <div className="absolute inset-0 bg-primary/30 flex items-center justify-center">
                            <CheckCircle className="w-4 h-4 text-white" />
                          </div>
                        )}
                      </div>
                    );
                  })}
                  {groupImages.length > 8 && (
                    <div className="aspect-square bg-muted border border-border flex items-center justify-center font-mono text-sm">
                      +{groupImages.length - 8}
                    </div>
                  )}
                </div>

                {/* Split Actions */}
                {isSplitting && (
                  <div className="p-3 bg-amber-50 border-t-2 border-amber-200">
                    <p className="text-xs text-amber-800 mb-2 font-mono">
                      Seleziona le foto da spostare in un nuovo gruppo
                    </p>
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        onClick={() => handleSplit(group.id)}
                        disabled={selectedImages.length === 0}
                        className="flex-1 bg-amber-500 text-white border-2 border-border text-xs"
                      >
                        Split ({selectedImages.length})
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => { setSplitMode(null); setSelectedImages([]); }}
                        className="border-2 border-border text-xs"
                      >
                        Cancel
                      </Button>
                    </div>
                  </div>
                )}

                {/* Draft Info */}
                <div className="p-3 border-t-2 border-border">
                  {draft ? (
                    <div>
                      <p className="font-mono text-xs text-muted-foreground mb-1">{draft.sku}</p>
                      <p className="text-sm font-medium truncate mb-2">{draft.title || "Untitled"}</p>
                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => navigate(`/draft/${draft.id}`)}
                          className="flex-1 border-2 border-border text-xs"
                        >
                          <Edit className="w-3 h-3 mr-1" />
                          Edit
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => navigate(`/draft/${draft.id}/preview`)}
                          className="flex-1 border-2 border-border text-xs"
                        >
                          <Eye className="w-3 h-3 mr-1" />
                          Preview
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2 text-amber-600">
                      <AlertTriangle className="w-4 h-4" />
                      <span className="text-xs font-mono">Draft non generato</span>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Unassigned Images */}
        {unassignedImages.length > 0 && (
          <div className="mt-8 bg-card border-2 border-border p-6 shadow-hard">
            <h3 className="font-heading font-bold uppercase mb-4 flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-amber-500" />
              Immagini non assegnate ({unassignedImages.length})
            </h3>
            <div className="grid grid-cols-8 sm:grid-cols-12 gap-2">
              {unassignedImages.map((img) => (
                <div key={img.id} className="aspect-square">
                  <img
                    src={img.url.startsWith('http') ? img.url : `${process.env.REACT_APP_BACKEND_URL}${img.url}`}
                    alt=""
                    className="w-full h-full object-cover border border-border"
                  />
                </div>
              ))}
            </div>
            <p className="mt-4 text-xs text-muted-foreground font-mono">
              Esegui l'auto-grouping o crea gruppi manualmente per assegnare queste immagini.
            </p>
          </div>
        )}
      </main>
    </div>
  );
}
