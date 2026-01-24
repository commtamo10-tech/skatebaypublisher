import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import Header from "../components/ui/Header";
import { mockApi } from "../lib/mockApi";

export default function DraftEditor() {
  const { id } = useParams();
  const [draft, setDraft] = useState(null);

  useEffect(() => {
    load();
  }, []);

  const load = async () => {
    const drafts = await mockApi.getDrafts();
    setDraft(drafts.find(d => d.id === id));
  };

  const generateAI = async () => {
    const text = await mockApi.generateDescription(draft);
    const updated = await mockApi.updateDraft(id, {
      description: text,
      status: "READY",
    });
    setDraft(updated);
  };

  const publish = async () => {
    const updated = await mockApi.publishDraft(id);
    setDraft(updated);
  };

  if (!draft) return null;

  return (
    <div className="min-h-screen bg-background">
      <Header />

      <main className="max-w-3xl mx-auto p-8 space-y-4">
        <h1 className="text-xl font-bold">{draft.title}</h1>

        <textarea
          value={draft.description}
          readOnly
          className="w-full h-40 border p-4"
        />

        <div className="flex gap-4">
          <button
            onClick={generateAI}
            className="bg-black text-white px-4 py-2"
          >
            Generate AI Text
          </button>

          <button
            onClick={publish}
            className="bg-green-600 text-white px-4 py-2"
          >
            Publish
          </button>
        </div>

        <div>Status: {draft.status}</div>
      </main>
    </div>
  );
}
