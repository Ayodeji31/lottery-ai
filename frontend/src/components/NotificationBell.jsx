import React, { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Bell, Trophy, Check } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import api from "@/lib/api";

export const NotificationBell = () => {
  const [data, setData] = useState({ unread_count: 0, notifications: [] });
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();

  const load = useCallback(() => {
    api.get("/notifications").then((r) => setData(r.data)).catch(() => {});
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 60000);
    return () => clearInterval(t);
  }, [load]);

  const markAllRead = async () => {
    await api.post("/notifications/read-all").catch(() => {});
    load();
  };

  const openItem = async (n) => {
    if (!n.read) await api.post(`/notifications/${n.id}/read`).catch(() => {});
    setOpen(false);
    navigate("/accuracy");
    load();
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          data-testid="notification-bell"
          className="relative flex items-center justify-center h-9 w-9 rounded-full text-muted-foreground hover:text-foreground hover:bg-white/5 transition-colors"
          aria-label="Notifications"
        >
          <Bell className="h-5 w-5" />
          {data.unread_count > 0 && (
            <span
              data-testid="notification-badge"
              className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] px-1 rounded-full bg-amber-500 text-black text-[10px] font-bold flex items-center justify-center"
            >
              {data.unread_count > 9 ? "9+" : data.unread_count}
            </span>
          )}
        </button>
      </PopoverTrigger>
      <PopoverContent
        align="end"
        className="w-80 p-0 bg-popover border-white/10"
        data-testid="notification-panel"
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-white/10">
          <h3 className="font-heading font-semibold text-sm">Notifications</h3>
          {data.unread_count > 0 && (
            <button
              data-testid="mark-all-read"
              onClick={markAllRead}
              className="text-xs text-sky-400 hover:text-sky-300 flex items-center gap-1"
            >
              <Check className="h-3 w-3" /> Mark all read
            </button>
          )}
        </div>
        <ScrollArea className="max-h-80">
          {data.notifications.length === 0 ? (
            <div className="px-4 py-10 text-center text-sm text-muted-foreground" data-testid="notification-empty">
              <Bell className="h-8 w-8 mx-auto mb-2 opacity-40" />
              No notifications yet. We'll alert you when a saved set would have won.
            </div>
          ) : (
            data.notifications.map((n) => (
              <button
                key={n.id}
                data-testid={`notification-item-${n.id}`}
                onClick={() => openItem(n)}
                className={`w-full text-left flex gap-3 px-4 py-3 border-b border-white/5 hover:bg-white/5 transition-colors ${
                  n.read ? "opacity-60" : ""
                }`}
              >
                <div className="h-9 w-9 rounded-full bg-amber-400/15 flex items-center justify-center shrink-0">
                  <Trophy className="h-4 w-4 text-amber-400" />
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-semibold truncate">{n.title}</p>
                  <p className="text-xs text-muted-foreground">{n.body}</p>
                </div>
                {!n.read && <span className="ml-auto mt-1 h-2 w-2 rounded-full bg-sky-400 shrink-0" />}
              </button>
            ))
          )}
        </ScrollArea>
      </PopoverContent>
    </Popover>
  );
};
