import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Sparkles, Eye, EyeOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/context/AuthContext";
import { formatApiError } from "@/lib/api";

export default function Auth() {
  const [mode, setMode] = useState("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { login, register } = useAuth();
  const navigate = useNavigate();

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (mode === "login") await login(email, password);
      else await register(name, email, password);
      navigate("/dashboard");
    } catch (err) {
      const status = err.response?.status;
      const detail = err.response?.data?.detail;
      if (!err.response) {
        setError("Can't reach the server. Please check your connection and try again.");
      } else if (status >= 500) {
        setError("The server is busy or waking up. Please wait a moment and try again.");
      } else {
        setError(formatApiError(detail) || "Something went wrong. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  const getSubmitLabel = () => {
    if (loading) return "Please wait…";
    return mode === "login" ? "Sign in" : "Create account";
  };
  const submitLabel = getSubmitLabel();

  return (
    <div className="min-h-screen grid-bg flex items-center justify-center px-4 py-12">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="w-full max-w-md rounded-3xl border border-white/10 bg-card/80 backdrop-blur-xl p-8 relative overflow-hidden"
      >
        <div className="absolute -top-24 -right-24 h-64 w-64 rounded-full bg-sky-500/20 blur-3xl pointer-events-none" aria-hidden="true" />
        <div className="flex items-center gap-2 mb-8">
          <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-sky-400 to-sky-600 flex items-center justify-center shadow-[0_0_16px_rgba(14,165,233,0.5)]">
            <Sparkles className="h-5 w-5 text-white" aria-hidden="true" />
          </div>
          <span className="font-heading font-bold text-xl tracking-tight">LottoLuck AI</span>
        </div>

        <h1 className="font-heading text-2xl font-bold tracking-tight mb-1">
          {mode === "login" ? "Welcome back" : "Create your account"}
        </h1>
        <p className="text-sm text-muted-foreground mb-6">
          {mode === "login" ? "Sign in to generate predictions." : "Start predicting in seconds."}
        </p>

        <form onSubmit={submit} className="space-y-4">
          {mode === "register" && (
            <div className="space-y-2">
              <Label htmlFor="name">Name</Label>
              <Input
                id="name"
                data-testid="auth-name-input"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Jane Doe"
                required
              />
            </div>
          )}
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              data-testid="auth-email-input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <div className="relative">
              <Input
                id="password"
                type={showPassword ? "text" : "password"}
                data-testid="auth-password-input"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                className="pr-11"
              />
              <button
                type="button"
                data-testid="toggle-password-visibility"
                onClick={() => setShowPassword((v) => !v)}
                aria-label={showPassword ? "Hide password" : "Show password"}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
              >
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>

          {error && (
            <p data-testid="auth-error" className="text-sm text-destructive">
              {error}
            </p>
          )}

          <Button
            type="submit"
            data-testid="auth-submit"
            disabled={loading}
            className="w-full rounded-full h-11 font-semibold hover:shadow-[0_0_20px_rgba(14,165,233,0.5)] transition-shadow"
          >
            {submitLabel}
          </Button>
        </form>

        <p className="text-sm text-muted-foreground text-center mt-6">
          {mode === "login" ? "No account yet?" : "Already have an account?"}{" "}
          <button
            data-testid="auth-toggle-mode"
            onClick={() => {
              setMode(mode === "login" ? "register" : "login");
              setError("");
            }}
            className="text-primary font-semibold hover:underline"
          >
            {mode === "login" ? "Sign up" : "Sign in"}
          </button>
        </p>
      </motion.div>
    </div>
  );
}
