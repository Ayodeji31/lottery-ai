import React from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Sparkles, LayoutDashboard, Bookmark, LogOut, Crown } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";

export const Navbar = () => {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  const links = [
    { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
    { to: "/saved", label: "Saved", icon: Bookmark },
  ];

  const handleLogout = async () => {
    await logout();
    navigate("/");
  };

  return (
    <header className="sticky top-0 z-50 bg-background/60 backdrop-blur-xl border-b border-white/10">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
        <Link to={user ? "/dashboard" : "/"} data-testid="nav-logo" className="flex items-center gap-2">
          <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-sky-400 to-sky-600 flex items-center justify-center shadow-[0_0_16px_rgba(14,165,233,0.5)]">
            <Sparkles className="h-5 w-5 text-white" aria-hidden="true" />
          </div>
          <span className="font-heading font-bold text-lg tracking-tight">LottoLuck AI</span>
        </Link>

        {user && (
          <nav className="flex items-center gap-1 sm:gap-2">
            {user.is_pro ? (
              <span
                data-testid="pro-badge"
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-amber-400/15 text-amber-300 border border-amber-400/30"
              >
                <Crown className="h-3.5 w-3.5" /> Pro
              </span>
            ) : (
              <Link to="/upgrade" data-testid="nav-upgrade">
                <Button
                  size="sm"
                  className="rounded-full bg-amber-500 hover:bg-amber-400 text-black font-semibold h-8"
                >
                  <Crown className="h-3.5 w-3.5 sm:mr-1.5" />
                  <span className="hidden sm:inline">Go Pro</span>
                </Button>
              </Link>
            )}
            {links.map((l) => {
              const active = location.pathname === l.to;
              const Icon = l.icon;
              return (
                <Link
                  key={l.to}
                  to={l.to}
                  data-testid={`nav-${l.label.toLowerCase()}`}
                  className={`flex items-center gap-2 px-3 py-2 rounded-full text-sm transition-colors ${
                    active ? "bg-primary/15 text-primary" : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  <Icon className="h-4 w-4" aria-hidden="true" />
                  <span className="hidden sm:inline">{l.label}</span>
                </Link>
              );
            })}
            <Button
              data-testid="nav-logout"
              variant="ghost"
              size="sm"
              onClick={handleLogout}
              className="rounded-full text-muted-foreground hover:text-foreground"
            >
              <LogOut className="h-4 w-4" aria-hidden="true" />
              <span className="hidden sm:inline ml-2">Logout</span>
            </Button>
          </nav>
        )}
      </div>
    </header>
  );
};
