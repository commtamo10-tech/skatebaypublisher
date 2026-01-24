const STORAGE_KEY = "skatebay_drafts";

function loadDrafts() {
  const raw = localStorage.getItem(STORAGE_KEY);
  return raw ? JSON.parse(raw) : [];
}

function saveDrafts(drafts) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(drafts));
}

export const mockApi = {
  // GET /drafts
  async getDrafts() {
    return loadDrafts();
  },

  // POST /drafts
  async createDraft(data) {
    const drafts = loadDrafts();
    const newDraft = {
      id: Date.now().toString(),
      title: data.title || "New eBay Listing",
      price: data.price || 59.99,
      status: "DRAFT",
      description: "",
      createdAt: new Date().toISOString(),
    };

    drafts.unshift(newDraft);
    saveDrafts(drafts);
    return newDraft;
  },

  // PUT /drafts/:id
  async updateDraft(id, updates) {
    const drafts = loadDrafts();
    const updated = drafts.map(d =>
      d.id === id ? { ...d, ...updates } : d
    );
    saveDrafts(updated);
    return updated.find(d => d.id === id);
  },

  // AI TEXT GENERATION (mock)
  async generateDescription(draft) {
    return `🔥 ${draft.title}

High-quality product perfect for eBay listings.

• Condition: Brand new  
• Fast shipping  
• Trusted seller  

Buy now and upgrade your setup today.`;
  },

  // PUBLISH (mock eBay)
  async publishDraft(id) {
    const drafts = loadDrafts();
    const updated = drafts.map(d =>
      d.id === id ? { ...d, status: "PUBLISHED" } : d
    );
    saveDrafts(updated);
    return updated.find(d => d.id === id);
  },
};
