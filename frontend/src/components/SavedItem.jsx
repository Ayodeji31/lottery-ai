import React from "react";
import { motion } from "framer-motion";
import { Trash2, Brain, Calculator } from "lucide-react";
import { BallRow } from "@/components/LotteryBall";
import { Button } from "@/components/ui/button";

const gameName = (g) => (g === "lotto" ? "UK Lotto" : "EuroMillions");

export const SavedItem = ({ item, index, onDelete }) => (
  <motion.div
    initial={{ opacity: 0, y: 12 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ delay: index * 0.05 }}
    className="rounded-2xl border border-white/10 bg-card/60 p-5 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4"
    data-testid={`saved-item-${item.id}`}
  >
    <div>
      <div className="flex items-center gap-2 mb-3">
        <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-primary/15 text-primary">
          {gameName(item.game)}
        </span>
        <span className="flex items-center gap-1 text-xs text-muted-foreground">
          {item.method === "ai" ? <Brain className="h-3 w-3" /> : <Calculator className="h-3 w-3" />}
          {item.method}
        </span>
      </div>
      <BallRow main={item.main_numbers} bonus={item.bonus_numbers} size="md" animate={false} />
      {item.reasoning && <p className="text-xs text-muted-foreground mt-2 max-w-md">{item.reasoning}</p>}
    </div>
    <Button
      data-testid={`delete-saved-${item.id}`}
      variant="ghost"
      size="icon"
      onClick={() => onDelete(item.id)}
      className="rounded-full text-muted-foreground hover:text-destructive self-end sm:self-auto"
    >
      <Trash2 className="h-4 w-4" />
    </Button>
  </motion.div>
);
