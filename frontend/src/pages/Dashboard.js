import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import api from "../lib/api";
import { Button } from "../components/ui/button";
import { toast } from "sonner";
import { Plus, FileText, Clock, CheckCircle, Circle } from "lucide-react";
import Header from "../components/ui/Header";

const ITEM_TYPES = {
  WHL: { label: "Wheels", icon: "🛞" },
  TRK: { label: "Trucks", icon: "🔧" },
  DCK: { label: "Decks", icon: "🛹" },
  APP: { label: "Apparel", icon: "👕" },
  MISC: { label: "Misc", icon: "📦" },
};

export default function Dashboard() {
  const navigate = useNavigate();
  const [drafts, setDrafts] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadDrafts();
  }, []);

  const loadDrafts = async () => {
    try {
      const res = await api.get("/drafts");
      setDrafts(res.data || []);
    } catch (err) {
      toast.error("Failed to load drafts");
      setDrafts([]);
    } finally {
      setLoading(false);
    }
  };

  const stats = {
    total: drafts.length,
    DRAFT: drafts.filter(d => d.status === "DRAFT").length,
    READY: drafts.filter(d => d.status === "READY").length,
    PUBLISHED: drafts.filter(d => d.status === "PUBLISHED").length,
  };

  return (
    <div className="min-h-screen bg-background">
      {/* HEADER CON LOGOUT */}
      <Header />

      <main className="max-w-6xl mx-auto px-6 py-8">
        {/* STATS */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <Stat label="Total" value={stats.total} icon={FileText} />
          <Stat label="Drafts" value={stats.DRAFT} icon={Clock} />
          <Stat label="Ready" value={stats.READY} icon={Circle} />
          <Stat label="Published" value={stats.PUBLISHED} icon={CheckCircle} />
        </div>

        {/* LISTA DRAFT */}
        {loading ? (
          <p className="font-mono">Loading...</p>
        ) : drafts.length === 0 ? (
          <div className="border-2 border-border p-12 text-center">
            <p className="font-bold uppercase mb-4">No drafts yet</p>
            <Button onClick={() => navigate("/new")}>
              <Plus className="w-4 h-4 mr-2" />
              Create first draft
            </Button>
          </div>
        ) : (
          <div className="space-y-3">
            {drafts.map(draft => {
              const type =
                ITEM_TYPES[draft.item_type] || {
                  label: draft.item_type,
                  icon: "📦",
                };

              return (
                <div
                  key={draft.id}
                  className="border-2 border-border p-4 cursor-pointer hover:bg-muted"
                  onClick={() => navigate(`/draft/${draft.id}`)}
                >
                  <div className="flex items-center gap-4">
                    <div className="text-3xl">{type.icon}</div>
                    <div className="flex-1">
                      <p className="font-bold uppercase">{type.label}</p>
                      <p className="font-mono text-sm">
                        ${draft.price?.toFixed(2)} · {draft.status}
                      </p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}

function Stat({ label, value, icon: Icon }) {
  return (
    <div className="border-2 border-border p-4 bg-card">
      <div className="flex justify-between items-center">
        <div>
          <p className="text-xs uppercase font-bold">{label}</p>
          <p className="text-3xl font-black">{value}</p>
        </div>
        <Icon className="w-8 h-8" />
      </div>
    </div>
  );
}
