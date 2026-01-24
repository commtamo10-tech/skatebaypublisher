import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Header from "../components/ui/Header";
import { mockApi } from "../lib/mockApi";

export default function Dashboard() {
  const navigate = useNavigate();
  const [drafts, setDrafts] = useState([]);

  useEffect(() => {
    load();
  }, []);

  const load = async () => {
    const data = await mockApi.getDrafts();
    setDrafts(data);
  };

  const createDraft = async () => {
    const draft = await mockApi.createDraft({
      title: "Skateboard Deck",
      price: 59.99,
    });
    navigate(`/draft/${draft.id}`);
  };

  return (
    <div className="min-h-screen bg-background">
      <Header />

      <main className="max-w-5xl mx-auto p-8">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-2xl font-black uppercase">Dashboard</h1>
          <button
            onClick={createDraft}
            className="bg-black text-white px-4 py-2 font-bold"
          >
            + New Draft
          </button>
        </div>

        {drafts.length === 0 ? (
          <p>No drafts yet</p>
        ) : (
          <div className="space-y-4">
            {drafts.map(d => (
              <div
                key={d.id}
                onClick={() => navigate(`/draft/${d.id}`)}
                className="border-2 p-4 cursor-pointer hover:bg-muted"
              >
                <div className="font-bold">{d.title}</div>
                <div className="text-sm">
                  ${d.price} · {d.status}
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
