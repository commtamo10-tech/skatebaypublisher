import axios from "axios";

const api = axios.create();

// MOCK TEMPORANEO BACKEND
api.get = async (url) => {
  if (url === "/drafts") {
    return {
      data: [
        {
          id: "1",
          title: "Skate Deck – Baker 8.0",
          status: "draft",
          sku: "BK-8001",
        },
        {
          id: "2",
          title: "Wheels – Spitfire Formula Four",
          status: "ready",
          sku: "SP-5400",
        },
      ],
    };
  }

  return { data: [] };
};

export default api;
