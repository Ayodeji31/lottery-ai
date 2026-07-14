import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Target, Trophy, TrendingUp, Crown, Loader2, Brain, Calculator } from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/context/AuthContext";
import api from "@/lib/api";

const gameName = (g) => (g === "lotto" ? "UK Lotto" : "EuroMillions");

const Ball = ({ n, matched, bonus }) => (
  <div
    className={`h-9 w-9 rounded-full flex items-center justify-center font-mono text-sm font-bold border transition-colors ${
      matched
        ? bonus
          ? "bg-amber-400 text-black border-amber-300 shadow-[0_0_12px_rgba(251,191,36,0.5)]"
          : "bg-sky-400 text-black border-sky-300 shadow-[0_0_12px_rgba(14,165,233,0.5)]"
        : "bg-white/5 text-muted-foreground border-white/10"
    }`}
  >
    {n}
  </div>
);

const SummaryCard = ({ icon: Icon, label, value, sub, color, testid }) => (
  <div className="rounded-2xl border border-white/10 bg-card/60 p-6" data-testid={testid}>
    <div className="flex items-center gap-2 mb-3">
      <Icon className={`h-5 w-5 ${color}`} />
      <span className="text-sm text-muted-foreground">{label}</span>
    </div>
    <p className="font-heading text-3xl font-extrabold">{value}</p>
    {sub && <p className="text-xs text-muted-foreground mt-1">{sub}</p>}
  </div>
);

export default function Accuracy() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [gated, setGated] = useState(false);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    api
      .get("/accuracy")
      .then((r) => setData(r.data))
      .catch((err) => {
        if (err.response?.status === 402) setGated(true);
        else setLoadError(true);
      });
  }, []);

  if (gated || (user && !user.is_pro)) {
    return (
      <div className="min-h-screen grid-bg">
        <Navbar />
        <main className="max-w-3xl mx-auto px-4 sm:px-6 py-16 text-center">
          <div className="inline-flex h-16 w-16 rounded-2xl bg-amber-400/15 items-center justify-center mb-6">
            <Crown className="h-8 w-8 text-amber-400" />
          </div>
          <h1 className="font-heading text-3xl font-bold tracking-tight mb-3">Accuracy Tracker is a Pro feature</h1>
          <p className="text-muted-foreground max-w-md mx-auto mb-8">
            See exactly how every set you've saved would have performed against real historical draws — best matches, prize hits and hit rate.
          </p>
          <Button
            data-testid="accuracy-upgrade-btn"
            onClick={() => navigate("/upgrade")}
            className="rounded-full bg-amber-500 hover:bg-amber-400 text-black font-semibold"
          >
            <Crown className="h-4 w-4 mr-2" /> Upgrade to Pro — £4.99/mo
          </Button>
        </main>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="min-h-screen grid-bg">
        <Navbar />
        {loadError ? (
          <div className="flex flex-col items-center justify-center py-24 text-muted-foreground gap-3" data-testid="accuracy-error">
            <p>Couldn't load your accuracy data. Please try again.</p>
            <Button variant="outline" className="rounded-full border-white/15" onClick={() => window.location.reload()}>
              Retry
            </Button>
          </div>
        ) : (
          <div className="flex items-center justify-center py-24 text-muted-foreground">
            <Loader2 className="h-6 w-6 animate-spin mr-2 text-primary" /> Crunching your results…
          </div>
        )}
      </div>
    );
  }

  const { summary, predictions } = data;
  const best = summary.best_ever;

  return (
    <div className="min-h-screen grid-bg">
      <Navbar />
      <main className="max-w-5xl mx-auto px-4 sm:px-6 py-8">
        <h1 className="font-heading text-3xl font-bold tracking-tight mb-1">Accuracy Tracker</h1>
        <p className="text-muted-foreground text-sm mb-8">
          Backtest: how your saved sets would have performed across real historical draws.
        </p>

        {summary.tracked === 0 ? (
          <div className="rounded-3xl border border-white/10 bg-card/60 p-12 text-center" data-testid="accuracy-empty">
            <Target className="h-10 w-10 mx-auto text-muted-foreground mb-4" />
            <p className="text-muted-foreground">Save some predictions first, then come back to see how they stack up.</p>
          </div>
        ) : (
          <>
            <div className="grid sm:grid-cols-3 gap-4 mb-8">
              <SummaryCard
                testid="summary-tracked"
                icon={Target}
                color="text-sky-400"
                label="Sets tracked"
                value={summary.tracked}
                sub={`${summary.total_draws_checked} draw checks`}
              />
              <SummaryCard
                testid="summary-hits"
                icon={Trophy}
                color="text-amber-400"
                label="Prize hits"
                value={summary.total_prize_hits}
                sub="Times a set won any tier"
              />
              <SummaryCard
                testid="summary-hitrate"
                icon={TrendingUp}
                color="text-emerald-400"
                label="Hit rate"
                value={`${summary.hit_rate}%`}
                sub={best ? `Best: ${best.prize || `Match ${best.main_matched}`}` : "—"}
              />
            </div>

            <div className="space-y-3" data-testid="accuracy-list">
              {predictions.map((p, i) => (
                <motion.div
                  key={p.id}
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.05 }}
                  className="rounded-2xl border border-white/10 bg-card/60 p-5"
                  data-testid={`accuracy-item-${p.id}`}
                >
                  <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-primary/15 text-primary">
                        {gameName(p.game)}
                      </span>
                      <span className="flex items-center gap-1 text-xs text-muted-foreground">
                        {p.method === "ai" ? <Brain className="h-3 w-3" /> : <Calculator className="h-3 w-3" />}
                        {p.method}
                      </span>
                    </div>
                    {p.best?.prize ? (
                      <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-amber-400/15 text-amber-300 border border-amber-400/30">
                        Best: {p.best.prize}
                      </span>
                    ) : (
                      <span className="text-xs text-muted-foreground">No prize tier hit</span>
                    )}
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    {p.main_numbers.map((n) => (
                      <Ball key={`m-${n}`} n={n} matched={p.best?.draw_main?.includes(n)} />
                    ))}
                    {p.bonus_numbers.length > 0 && <span className="text-muted-foreground font-mono px-1">+</span>}
                    {p.bonus_numbers.map((n) => (
                      <Ball key={`b-${n}`} n={n} bonus matched={p.best?.draw_bonus?.includes(n)} />
                    ))}
                  </div>

                  {p.best && (
                    <p className="text-xs text-muted-foreground mt-3">
                      Best match: <span className="text-foreground font-semibold">{p.best.main_matched} number{p.best.main_matched !== 1 ? "s" : ""}</span>
                      {p.best.bonus_matched > 0 && ` + ${p.best.bonus_matched} bonus`} vs draw on {p.best.draw_date}
                      {" · "}
                      {p.prize_hits} prize hit{p.prize_hits !== 1 ? "s" : ""} across {p.draws_checked} draws
                    </p>
                  )}
                </motion.div>
              ))}
            </div>
          </>
        )}

        <p className="text-center text-xs text-muted-foreground mt-8">
          Backtesting shows historical performance only. Past results never guarantee future outcomes. Play responsibly · 18+
        </p>
      </main>
    </div>
  );
}
