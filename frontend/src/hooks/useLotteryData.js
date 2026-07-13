import { useEffect, useState, useCallback } from "react";
import api from "@/lib/api";

export function useLotteryData(active) {
  const [games, setGames] = useState([]);
  const [stats, setStats] = useState(null);
  const [draws, setDraws] = useState([]);

  useEffect(() => {
    let cancelled = false;
    api.get("/games").then((r) => {
      if (!cancelled) setGames(r.data);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const loadGame = useCallback((game) => {
    setStats(null);
    setDraws([]);
    api.get(`/stats/${game}`).then((r) => setStats(r.data));
    api.get(`/draws/${game}?limit=15`).then((r) => setDraws(r.data));
  }, []);

  useEffect(() => {
    loadGame(active);
  }, [active, loadGame]);

  return { games, stats, draws };
}
