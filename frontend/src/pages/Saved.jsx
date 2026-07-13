import React, { useEffect, useState, useCallback } from "react";
import { Bookmark } from "lucide-react";
import { toast } from "sonner";
import { Navbar } from "@/components/Navbar";
import { SavedItem } from "@/components/SavedItem";
import api, { formatApiError } from "@/lib/api";

export default function Saved() {
  const [items, setItems] = useState(null);

  const load = useCallback(() => api.get("/saved").then((r) => setItems(r.data)), []);

  useEffect(() => {
    load();
  }, [load]);

  const remove = async (id) => {
    try {
      await api.delete(`/saved/${id}`);
      setItems((prev) => prev.filter((i) => i.id !== id));
      toast.success("Removed");
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail));
    }
  };

  return (
    <div className="min-h-screen grid-bg">
      <Navbar />
      <main className="max-w-5xl mx-auto px-4 sm:px-6 py-8">
        <h1 className="font-heading text-3xl font-bold tracking-tight mb-1">Saved Predictions</h1>
        <p className="text-muted-foreground text-sm mb-8">Your bookmarked number sets.</p>

        {items === null && <p className="text-muted-foreground">Loading…</p>}

        {items && items.length === 0 && (
          <div className="rounded-3xl border border-white/10 bg-card/60 p-12 text-center" data-testid="saved-empty">
            <Bookmark className="h-10 w-10 mx-auto text-muted-foreground mb-4" aria-hidden="true" />
            <p className="text-muted-foreground">No saved predictions yet. Generate some in the Prediction Lab.</p>
          </div>
        )}

        <div className="space-y-3" data-testid="saved-list">
          {items?.map((it, i) => (
            <SavedItem key={it.id} item={it} index={i} onDelete={remove} />
          ))}
        </div>
      </main>
    </div>
  );
}
