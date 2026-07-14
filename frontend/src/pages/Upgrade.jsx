import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Check, Crown, Sparkles, Loader2, ArrowLeft, CalendarClock, XCircle } from "lucide-react";
import { toast } from "sonner";
import { Navbar } from "@/components/Navbar";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/context/AuthContext";
import api, { formatApiError } from "@/lib/api";

const freePerks = [
  "UK National Lottery statistics",
  "Hot / cold / overdue analysis",
  "1 AI prediction per day",
];

const proPerks = [
  "Unlimited AI predictions",
  "All games — UK Lotto + EuroMillions",
  "Prediction accuracy tracker",
  "Priority AI number sets",
  "Cancel anytime",
];

export default function Upgrade() {
  const { user, refreshUser } = useAuth();
  const [loading, setLoading] = useState(false);
  const [sub, setSub] = useState(null);
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    api.get("/payments/subscription").then((r) => setSub(r.data)).catch(() => {});
  }, [user]);

  const startCheckout = async () => {
    setLoading(true);
    try {
      const { data } = await api.post("/payments/checkout", {
        package_id: "pro_monthly",
        origin_url: window.location.origin,
      });
      window.location.href = data.url;
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || "Could not start checkout");
      setLoading(false);
    }
  };

  const cancelSub = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/payments/subscription/cancel");
      setSub(data);
      await refreshUser();
      toast.success("Auto-renew turned off. You keep Pro until your period ends.");
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail));
    } finally {
      setBusy(false);
    }
  };

  const resumeSub = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/payments/subscription/resume");
      setSub(data);
      await refreshUser();
      toast.success("Auto-renew turned back on.");
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail));
    } finally {
      setBusy(false);
    }
  };

  const renewDate = sub?.renews_at
    ? new Date(sub.renews_at).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })
    : null;

  return (
    <div className="min-h-screen grid-bg">
      <Navbar />
      <main className="max-w-5xl mx-auto px-4 sm:px-6 py-10">
        <button
          data-testid="upgrade-back"
          onClick={() => navigate("/dashboard")}
          className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground mb-8 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" /> Back to dashboard
        </button>

        <div className="text-center mb-12">
          <div className="inline-flex items-center gap-2 rounded-full border border-amber-400/30 bg-amber-400/10 px-4 py-1.5 text-sm text-amber-300 mb-4">
            <Crown className="h-4 w-4" /> Go Pro
          </div>
          <h1 className="font-heading font-extrabold tracking-tight text-4xl sm:text-5xl">
            Unlock the full engine
          </h1>
          <p className="mt-4 text-muted-foreground max-w-lg mx-auto">
            More games, unlimited AI number sets and accuracy tracking. For entertainment — no system can guarantee a win.
          </p>
        </div>

        {user?.is_pro && sub && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            className="max-w-2xl mx-auto mb-10 rounded-3xl border border-amber-400/30 bg-card/80 p-6 sm:p-8"
            data-testid="manage-subscription"
          >
            <div className="flex items-center gap-2 mb-4">
              <Crown className="h-5 w-5 text-amber-400" />
              <h2 className="font-heading text-xl font-bold">Your Pro subscription</h2>
            </div>
            <div className="grid sm:grid-cols-2 gap-4 mb-6">
              <div className="rounded-2xl bg-white/5 border border-white/10 p-4">
                <p className="text-xs text-muted-foreground mb-1">Status</p>
                <p className="font-semibold" data-testid="sub-status">
                  {sub.status === "active" ? "Active · auto-renews" : "Canceled · ends soon"}
                </p>
              </div>
              <div className="rounded-2xl bg-white/5 border border-white/10 p-4">
                <p className="text-xs text-muted-foreground mb-1 flex items-center gap-1">
                  <CalendarClock className="h-3 w-3" /> {sub.auto_renew ? "Renews on" : "Access until"}
                </p>
                <p className="font-semibold" data-testid="sub-renew-date">
                  {renewDate} · {sub.days_remaining} day{sub.days_remaining !== 1 ? "s" : ""} left
                </p>
              </div>
            </div>
            {sub.auto_renew ? (
              <Button
                data-testid="cancel-subscription-btn"
                variant="outline"
                onClick={cancelSub}
                disabled={busy}
                className="rounded-full border-white/15 text-muted-foreground hover:text-destructive"
              >
                {busy ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <XCircle className="h-4 w-4 mr-2" />}
                Cancel subscription
              </Button>
            ) : (
              <Button
                data-testid="resume-subscription-btn"
                onClick={resumeSub}
                disabled={busy}
                className="rounded-full bg-amber-500 hover:bg-amber-400 text-black font-semibold"
              >
                {busy ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Crown className="h-4 w-4 mr-2" />}
                Resume auto-renew
              </Button>
            )}
            <p className="text-xs text-muted-foreground mt-4">
              Billing is £4.99 per 30-day period. Canceling keeps your Pro access until the current period ends.
            </p>
          </motion.div>
        )}

        <div className="grid md:grid-cols-2 gap-6 items-stretch">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-3xl border border-white/10 bg-card/60 p-8 flex flex-col"
            data-testid="plan-free"
          >
            <div className="flex items-center gap-2 mb-2">
              <Sparkles className="h-5 w-5 text-sky-400" />
              <h2 className="font-heading text-xl font-bold">Free</h2>
            </div>
            <p className="font-heading text-4xl font-extrabold mb-6">£0</p>
            <ul className="space-y-3 flex-1">
              {freePerks.map((p) => (
                <li key={p} className="flex items-start gap-3 text-sm text-muted-foreground">
                  <Check className="h-4 w-4 text-sky-400 mt-0.5 shrink-0" /> {p}
                </li>
              ))}
            </ul>
            <Button disabled variant="outline" className="mt-8 rounded-full border-white/15 w-full">
              Your current plan
            </Button>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="relative rounded-3xl border-2 border-sky-500/60 bg-card/80 p-8 flex flex-col overflow-hidden"
            data-testid="plan-pro"
          >
            <div className="absolute -top-24 -right-24 h-64 w-64 rounded-full bg-sky-500/20 blur-3xl pointer-events-none" aria-hidden="true" />
            <div className="flex items-center gap-2 mb-2">
              <Crown className="h-5 w-5 text-amber-400" />
              <h2 className="font-heading text-xl font-bold">Pro</h2>
            </div>
            <p className="font-heading text-4xl font-extrabold mb-1">
              £4.99<span className="text-base font-medium text-muted-foreground">/month</span>
            </p>
            <p className="text-xs text-muted-foreground mb-6">Billed monthly · Cancel anytime</p>
            <ul className="space-y-3 flex-1">
              {proPerks.map((p) => (
                <li key={p} className="flex items-start gap-3 text-sm">
                  <Check className="h-4 w-4 text-amber-400 mt-0.5 shrink-0" /> {p}
                </li>
              ))}
            </ul>
            {user?.is_pro ? (
              <Button disabled className="mt-8 rounded-full w-full bg-amber-500 hover:bg-amber-500">
                <Crown className="h-4 w-4 mr-2" /> You're a Pro member
              </Button>
            ) : (
              <Button
                data-testid="upgrade-checkout-btn"
                onClick={startCheckout}
                disabled={loading}
                className="mt-8 rounded-full w-full font-semibold hover:shadow-[0_0_24px_rgba(14,165,233,0.5)] transition-shadow"
              >
                {loading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Crown className="h-4 w-4 mr-2" />}
                Upgrade to Pro
              </Button>
            )}
          </motion.div>
        </div>

        <p className="text-center text-xs text-muted-foreground mt-8">
          Test mode — use card 4242 4242 4242 4242, any future date & CVC. No real charge.
        </p>
      </main>
    </div>
  );
}
