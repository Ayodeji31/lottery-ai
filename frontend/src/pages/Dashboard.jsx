import React, { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { BarChart, Bar, ResponsiveContainer, XAxis, Tooltip, Cell } from "recharts";
import { Flame, Snowflake, Clock, Brain, Calculator, Bookmark, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Navbar } from "@/components/Navbar";
import { BallRow } from "@/components/LotteryBall";
import { Button } from "@/components/ui/button";
import api, { formatApiError } from "@/lib/api";

const GameToggle = ({ games, active, onChange }) => (
  <div className="inline-flex rounded-full border border-white/10 bg-card/60 p-1" data-testid="game-toggle">
    {games.map((g) => (
      <button
        key={g.id}
        data-testid={`game-tab-${g.id}`}
        onClick={() => onChange(g.id)}
        className={`px-4 sm:px-6 py-2 rounded-full text-sm font-semibold transition-colors ${
          active === g.id ? "bg-primary text-primary-foreground shadow-[0_0_16px_rgba(14,165,233,0.4)]" : "text-muted-foreground hover:text-foreground"
        }`}
      >
        {g.name}
      </button>
    ))}
  </div>
);

const StatCard = ({ icon: Icon, title, color, items, testid }) => (
  <div className="rounded-2xl border border-white/10 bg-card/60 p-6" data-testid={testid}>
    <div className="flex items-center gap-2 mb-4">
      <Icon className={`h-5 w-5 ${color}`} aria-hidden="true" />
      <h3 className="font-heading font-semibold">{title}</h3>
    </div>
    <div className="flex flex-wrap gap-2">
      {items.map((n) => (
        <div key={n.number} className="flex flex-col items-center">
          <div className="h-11 w-11 rounded-full bg-white/5 border border-white/10 flex items-center justify-center font-mono font-bold">
            {n.number}
          </div>
          <span className="text-[10px] text-muted-foreground mt-1 font-mono">
            {title === "Overdue" ? `${n.draws_ago}×` : `${n.percentage}%`}
          </span>
        </div>
      ))}
    </div>
  </div>
);

export default function Dashboard() {
  const [games, setGames] = useState([]);
  const [active, setActive] = useState("lotto");
  const [stats, setStats] = useState(null);
  const [draws, setDraws] = useState([]);
  const [preds, setPreds] = useState(null);
  const [summary, setSummary] = useState("");
  const [method, setMethod] = useState("");
  const [loadingPred, setLoadingPred] = useState("");

  useEffect(() => {
    api.get("/games").then((r) => setGames(r.data));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    setStats(null);
    setDraws([]);
    setPreds(null);
    api.get(`/stats/${active}`).then((r) => setStats(r.data));
    api.get(`/draws/${active}?limit=15`).then((r) => setDraws(r.data));
  }, [active]);

  const generate = async (kind) => {
    setLoadingPred(kind);
    setPreds(null);
    try {
      const { data } = await api.post(`/predict/${kind}/${active}`);
      setPreds(data.predictions);
      setSummary(data.summary || "");
      setMethod(data.method);
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || "Failed to generate");
    } finally {
      setLoadingPred("");
    }
  };

  const savePred = async (p) => {
    try {
      await api.post("/saved", {
        game: active,
        method,
        main_numbers: p.main_numbers,
        bonus_numbers: p.bonus_numbers,
        reasoning: p.reasoning || summary,
      });
      toast.success("Saved to your predictions");
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail));
    }
  };

  const chartData = stats
    ? stats.main_frequency.map((f) => ({ number: f.number, count: f.count }))
    : [];
  const maxCount = Math.max(...chartData.map((d) => d.count), 1);

  return (
    <div className="min-h-screen grid-bg">
      <Navbar />
      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-8">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8">
          <div>
            <h1 className="font-heading text-3xl font-bold tracking-tight">Prediction Lab</h1>
            <p className="text-muted-foreground text-sm mt-1">
              {stats ? `Analysing ${stats.total_draws} real historical draws` : "Loading draw history…"}
            </p>
          </div>
          <GameToggle games={games} active={active} onChange={setActive} />
        </div>

        {/* Generators */}
        <div className="grid lg:grid-cols-12 gap-4 mb-4">
          <motion.div
            layout
            className="lg:col-span-8 rounded-3xl border border-white/10 bg-card/80 p-6 sm:p-8 relative overflow-hidden"
            data-testid="predictor-card"
          >
            <div className="absolute -top-32 -right-32 h-72 w-72 rounded-full bg-sky-500/10 blur-3xl" aria-hidden="true" />
            <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
              <div>
                <p className="font-mono text-xs uppercase tracking-widest text-sky-300">Generate</p>
                <h2 className="font-heading text-2xl font-bold tracking-tight">Your Number Sets</h2>
              </div>
              <div className="flex gap-2">
                <Button
                  data-testid="generate-statistical"
                  variant="outline"
                  onClick={() => generate("statistical")}
                  disabled={!!loadingPred}
                  className="rounded-full border-white/15"
                >
                  {loadingPred === "statistical" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Calculator className="h-4 w-4" />}
                  <span className="ml-2">Statistical</span>
                </Button>
                <Button
                  data-testid="generate-ai"
                  onClick={() => generate("ai")}
                  disabled={!!loadingPred}
                  className="rounded-full hover:shadow-[0_0_20px_rgba(14,165,233,0.5)] transition-shadow"
                >
                  {loadingPred === "ai" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Brain className="h-4 w-4" />}
                  <span className="ml-2">AI Predict</span>
                </Button>
              </div>
            </div>

            {!preds && !loadingPred && (
              <div className="text-center py-12 text-muted-foreground" data-testid="predictor-empty">
                Pick a method above to reveal your suggested numbers.
              </div>
            )}
            {loadingPred && (
              <div className="text-center py-12 text-muted-foreground">
                <Loader2 className="h-6 w-6 animate-spin mx-auto mb-3 text-primary" />
                Crunching the numbers…
              </div>
            )}

            {preds && (
              <div className="space-y-4" data-testid="prediction-results">
                {summary && <p className="text-sm text-muted-foreground mb-2">{summary}</p>}
                {preds.map((p, i) => (
                  <motion.div
                    key={`${active}-${p.main_numbers.join("-")}-${i}`}
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.15 }}
                    className="rounded-2xl border border-white/10 bg-white/5 p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4"
                    data-testid={`prediction-set-${i}`}
                  >
                    <div>
                      <BallRow main={p.main_numbers} bonus={p.bonus_numbers} size="md" />
                      {p.reasoning && <p className="text-xs text-muted-foreground mt-2">{p.reasoning}</p>}
                    </div>
                    <Button
                      data-testid={`save-prediction-${i}`}
                      variant="ghost"
                      size="sm"
                      onClick={() => savePred(p)}
                      className="rounded-full text-sky-300 hover:text-sky-200 self-start sm:self-auto"
                    >
                      <Bookmark className="h-4 w-4 mr-1" /> Save
                    </Button>
                  </motion.div>
                ))}
              </div>
            )}
          </motion.div>

          <div className="lg:col-span-4 grid gap-4">
            {stats && (
              <StatCard testid="stat-hot" icon={Flame} color="text-orange-400" title="Hot" items={stats.hot} />
            )}
            {stats && (
              <StatCard testid="stat-overdue" icon={Clock} color="text-sky-400" title="Overdue" items={stats.overdue} />
            )}
          </div>
        </div>

        <div className="grid lg:grid-cols-12 gap-4 mb-4">
          {stats && (
            <StatCard testid="stat-cold" icon={Snowflake} color="text-cyan-300" title="Cold" items={stats.cold} />
          )}
          <div className="lg:col-span-8 rounded-2xl border border-white/10 bg-card/60 p-6" data-testid="frequency-chart">
            <h3 className="font-heading font-semibold mb-4">Number Frequency</h3>
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={chartData}>
                <XAxis dataKey="number" tick={{ fill: "#64748b", fontSize: 10 }} interval={4} axisLine={false} tickLine={false} />
                <Tooltip
                  cursor={{ fill: "rgba(14,165,233,0.08)" }}
                  contentStyle={{ background: "#0f172a", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 12, color: "#f8fafc" }}
                />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {chartData.map((d) => (
                    <Cell key={d.number} fill={`rgba(14,165,233,${0.3 + (d.count / maxCount) * 0.7})`} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Recent draws */}
        <div className="rounded-2xl border border-white/10 bg-card/60 p-6" data-testid="recent-draws">
          <h3 className="font-heading font-semibold mb-4">Recent Draws</h3>
          <div className="space-y-2">
            {draws.map((d) => (
              <div
                key={d.draw_number}
                className="flex flex-col sm:flex-row sm:items-center gap-3 sm:gap-6 rounded-xl px-3 py-3 hover:bg-white/5 transition-colors hover:-translate-y-[2px]"
                data-testid={`draw-row-${d.draw_number}`}
              >
                <span className="font-mono text-xs text-muted-foreground w-24 shrink-0">{d.draw_date}</span>
                <BallRow main={d.main_numbers} bonus={d.bonus_numbers} size="sm" animate={false} />
              </div>
            ))}
            {draws.length === 0 && <p className="text-sm text-muted-foreground">Loading…</p>}
          </div>
        </div>

        <p className="text-center text-xs text-muted-foreground mt-8">
          Predictions are for entertainment only. Lottery draws are random and cannot be guaranteed. Play responsibly · 18+
        </p>
      </main>
    </div>
  );
}
