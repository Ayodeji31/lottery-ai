import React from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { Sparkles, BarChart3, Brain, ShieldCheck, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { BallRow } from "@/components/LotteryBall";
import { useAuth } from "@/context/AuthContext";

const features = [
  { icon: BarChart3, title: "Statistical Engine", desc: "Hot, cold & overdue number analysis across real historical draws." },
  { icon: Brain, title: "AI Predictions", desc: "An AI analyst studies frequency patterns to craft balanced number sets." },
  { icon: ShieldCheck, title: "Real Draw Data", desc: "Live UK Lotto & EuroMillions results scraped from official history." },
];

const FeatureGrid = () => (
  <div className="grid sm:grid-cols-3 gap-4 mt-20">
    {features.map((f, i) => {
      const Icon = f.icon;
      return (
        <motion.div
          key={f.title}
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: i * 0.1 }}
          className="rounded-2xl border border-white/10 bg-card/60 p-6"
        >
          <div className="h-11 w-11 rounded-xl bg-primary/15 flex items-center justify-center mb-4">
            <Icon className="h-5 w-5 text-primary" aria-hidden="true" />
          </div>
          <h3 className="font-heading font-semibold text-lg mb-2">{f.title}</h3>
          <p className="text-sm text-muted-foreground">{f.desc}</p>
        </motion.div>
      );
    })}
  </div>
);

export default function Landing() {
  const { user } = useAuth();
  const cta = user ? "/dashboard" : "/auth";

  return (
    <div className="min-h-screen grid-bg">
      <header className="sticky top-0 z-50 bg-background/60 backdrop-blur-xl border-b border-white/10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-sky-400 to-sky-600 flex items-center justify-center shadow-[0_0_16px_rgba(14,165,233,0.5)]">
              <Sparkles className="h-5 w-5 text-white" aria-hidden="true" />
            </div>
            <span className="font-heading font-bold text-lg tracking-tight">LottoLuck AI</span>
          </div>
          <Link to="/auth" data-testid="header-signin">
            <Button variant="ghost" className="rounded-full">Sign in</Button>
          </Link>
        </div>
      </header>

      <section className="max-w-7xl mx-auto px-4 sm:px-6 pt-16 sm:pt-24 pb-16">
        <div className="grid lg:grid-cols-2 gap-12 items-center">
          <div>
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6 }}
              className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-1.5 text-sm text-sky-300 mb-6"
            >
              <Sparkles className="h-4 w-4" aria-hidden="true" />
              AI + Statistics for UK Lotto & EuroMillions
            </motion.div>
            <motion.h1
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.1 }}
              className="font-heading font-extrabold tracking-tight text-4xl sm:text-5xl lg:text-6xl leading-[1.05]"
            >
              Predict smarter.
              <span className="block bg-gradient-to-r from-sky-300 to-sky-500 bg-clip-text text-transparent">
                Play the numbers.
              </span>
            </motion.h1>
            <motion.p
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.2 }}
              className="mt-6 text-base sm:text-lg text-muted-foreground max-w-lg"
            >
              Generate data-driven number suggestions using real historical draws, frequency analytics and an AI prediction engine. For entertainment — no system can guarantee a win.
            </motion.p>
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.3 }}
              className="mt-8 flex flex-wrap gap-3"
            >
              <Link to={cta} data-testid="hero-get-started">
                <Button size="lg" className="rounded-full h-12 px-8 text-base font-semibold hover:shadow-[0_0_24px_rgba(14,165,233,0.5)] transition-shadow">
                  Get started free
                  <ArrowRight className="ml-2 h-5 w-5" aria-hidden="true" />
                </Button>
              </Link>
            </motion.div>
          </div>

          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.7, delay: 0.2 }}
            className="relative rounded-3xl border border-white/10 bg-card/80 backdrop-blur-xl p-8 overflow-hidden"
          >
            <div className="absolute -top-24 -right-24 h-64 w-64 rounded-full bg-sky-500/20 blur-3xl" aria-hidden="true" />
            <p className="font-mono text-xs uppercase tracking-widest text-sky-300 mb-1">AI Suggested Set</p>
            <p className="font-heading text-xl font-bold mb-6">EuroMillions</p>
            <div className="space-y-5">
              <BallRow main={[7, 14, 23, 38, 44]} bonus={[3, 9]} size="md" />
              <BallRow main={[5, 11, 27, 33, 49]} bonus={[2, 12]} size="md" />
              <BallRow main={[9, 18, 30, 41, 47]} bonus={[6, 10]} size="md" />
            </div>
            <div className="mt-6 pt-4 border-t border-white/10 text-sm text-muted-foreground">
              Balanced blend of hot & overdue numbers.
            </div>
          </motion.div>
        </div>

        <FeatureGrid />
      </section>

      <footer className="border-t border-white/10 py-8 text-center text-sm text-muted-foreground">
        LottoLuck AI · For entertainment only · Please play responsibly · 18+
      </footer>
    </div>
  );
}
