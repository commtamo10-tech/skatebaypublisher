const handleCreateDraft = async () => {
  setLoading(true);

  try {
    // Upload images
    const uploadedUrls = await uploadImages();

    // Create draft
    await api.post("/drafts", {
      item_type: itemType,
      category_id: categoryId,
      price: parseFloat(price),
      image_urls: uploadedUrls,
      condition: "NEW"
    });

    toast.success("Draft created successfully!");
    navigate("/");   // ⬅⬅⬅ QUESTA È LA RIGA CHIAVE

  } catch (error) {
    toast.error(
      error.response?.data?.detail ||
      error.message ||
      "Failed to create draft"
    );
  } finally {
    setLoading(false); // ⬅⬅⬅ SBLOCCA IL BOTTONE
  }
};
