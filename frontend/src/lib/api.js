import axios from "axios";

const api = axios.create();

// MOCK ALLINEATO A EMERGENT
api.get = async (url) => {
  if (url === "/drafts") {
    return {
      data: [
        {
          id: "1",
          title: "Skate Deck Baker 8.0",
          sku: "BK-8001",
          price: 59.99,
          status: "draft",
        },
        {
          id: "2",
          title: "Spitfire Formula Four Wheels",
          sku: "SP-5400",
          price: 44.99,
          status: "ready",
        },
      ],
    };
  }

  return { data: [] };
};

export default api;
