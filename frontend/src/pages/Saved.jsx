import React, { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Trash2, Bookmark, Brain, Calculator } from "lucide-react";
import { toast } from "sonner";
import { Navbar } from "@/components/Navbar";
import { BallRow } from "@/components/LotteryBall";
import { Button } from "@/components/ui/button";
import api, { formatApiError } from "@/lib/api";

const gameName = (g) => (g === "lotto" ? "UK Lotto" : "EuroMillions");

export default function Saved() {
  const [items, setItems] = useState(null);

  const load = () => api.get("/saved").then((r) => setItems(r.data));

  useEffect(() => {
    load();
  }, []);

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
            <motion.div
              key={it.id}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
              className="rounded-2xl border border-white/10 bg-card/60 p-5 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4"
              data-testid={`saved-item-${it.id}`}
            >
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-primary/15 text-primary">
                    {gameName(it.game)}
                  </span>
                  <span className="flex items-center gap-1 text-xs text-muted-foreground">
                    {it.method === "ai" ? <Brain className="h-3 w-3" /> : <Calculator className="h-3 w-3" />}
                    {it.method}
                  </span>
                </div>
                <BallRow main={it.main_numbers} bonus={it.bonus_numbers} size="md" animate={false} />
                {it.reasoning && <p className="text-xs text-muted-foreground mt-2 max-w-md">{it.reasoning}</p>}
              </div>
              <Button
                data-testid={`delete-saved-${it.id}`}
                variant="ghost"
                size="icon"
                onClick={() => remove(it.id)}
                className="rounded-full text-muted-foreground hover:text-destructive self-end sm:self-auto"
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </motion.div>
          ))}
        </div>
      </main>
    </div>
  );
}
