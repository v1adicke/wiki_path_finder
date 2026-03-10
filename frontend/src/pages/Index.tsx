import { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Search, Sparkles, ArrowUpDown } from "lucide-react";
import { startSearch, SearchResult, SearchStatus } from "@/lib/api";
import { SearchLoader } from "@/components/SearchLoader";
import { PathTimeline } from "@/components/PathTimeline";

const SearchPage = () => {
  const [startArticle, setStartArticle] = useState("");
  const [endArticle, setEndArticle] = useState("");
  const [status, setStatus] = useState<SearchStatus>("idle");
  const [result, setResult] = useState<SearchResult | null>(null);
  const [errorText, setErrorText] = useState<string | null>(null);

  const isSearching = status === "heuristic" || status === "exact";

  const handleSwapArticles = useCallback(() => {
    if (isSearching) return;
    setStartArticle(endArticle);
    setEndArticle(startArticle);
  }, [endArticle, isSearching, startArticle]);

  const handleSearch = useCallback(async () => {
    if (!startArticle.trim() || !endArticle.trim() || isSearching) return;
    setResult(null);
    setErrorText(null);
    try {
      const res = await startSearch(startArticle.trim(), endArticle.trim(), (p) => {
        setStatus(p.status);
        if (p.result) setResult(p.result);
      });
      setResult(res);
      if (res.error) {
        setErrorText(res.error);
        setStatus("error");
        return;
      }
      if (!res.path || res.path.length === 0) {
        setErrorText("Путь не найден за отведенное время. Попробуйте другую пару статей.");
      }
      setStatus("done");
    } catch (err) {
      setErrorText(err instanceof Error ? err.message : "Произошла ошибка поиска");
      setStatus("error");
    }
  }, [startArticle, endArticle, isSearching]);

  return (
    <div className="relative h-[calc(100vh-3.5rem)] flex flex-col items-center justify-center px-4 overflow-hidden">
      <div className="absolute inset-0 bg-radial-glow pointer-events-none" />
      <div className="absolute inset-0 bg-dot pointer-events-none opacity-40" />

      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, ease: [0.25, 0.46, 0.45, 0.94] }}
        className="relative z-10 w-full max-w-2xl"
      >
        <div className="text-center mb-12">
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.2, duration: 0.6 }}
            className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-border bg-secondary/50 text-xs font-mono text-muted-foreground mb-6"
          >
            <Sparkles className="w-3 h-3 text-primary" />
            Bidirectional BFS · Wikipedia RU
          </motion.div>
          <h1 className="text-5xl sm:text-6xl font-bold tracking-tight mb-4">
            Wiki <span className="text-gradient-primary">Path</span> Finder
          </h1>
          <p className="text-muted-foreground text-lg max-w-md mx-auto">
            Найдите кратчайший путь между любыми двумя статьями русской Википедии
          </p>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4, duration: 0.6 }}
          className="relative rounded-2xl border border-border bg-card/80 backdrop-blur-sm p-6 glow-primary"
        >
          <div className="space-y-4">
            <div className="relative group">
              <label className="block text-xs font-mono text-muted-foreground mb-2 uppercase tracking-wider">
                Начальная статья
              </label>
              <input
                type="text"
                value={startArticle}
                onChange={(e) => setStartArticle(e.target.value)}
                placeholder="Например: Москва"
                disabled={isSearching}
                className="w-full bg-secondary/50 border border-border rounded-lg px-4 py-3 text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-primary/50 focus:glow-border transition-all font-mono text-sm"
                onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              />
            </div>

            <div className="flex items-center justify-center">
              <div className="h-px flex-1 bg-border" />
              <motion.button
                whileTap={{ scale: 0.95 }}
                whileHover={{ scale: 1.05 }}
                type="button"
                onClick={handleSwapArticles}
                disabled={isSearching}
                className="mx-3 p-2 rounded-md border border-border bg-secondary/40 text-muted-foreground hover:text-foreground hover:bg-secondary/60 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                aria-label="Поменять местами начальную и конечную статьи"
                title="Поменять местами"
              >
                <ArrowUpDown className="w-4 h-4" />
              </motion.button>
              <div className="h-px flex-1 bg-border" />
            </div>

            <div className="relative group">
              <label className="block text-xs font-mono text-muted-foreground mb-2 uppercase tracking-wider">
                Конечная статья
              </label>
              <input
                type="text"
                value={endArticle}
                onChange={(e) => setEndArticle(e.target.value)}
                placeholder="Например: Россия"
                disabled={isSearching}
                className="w-full bg-secondary/50 border border-border rounded-lg px-4 py-3 text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-primary/50 transition-all font-mono text-sm"
                onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              />
            </div>

            <motion.button
              whileHover={{ scale: 1.01 }}
              whileTap={{ scale: 0.98 }}
              onClick={handleSearch}
              disabled={isSearching || !startArticle.trim() || !endArticle.trim()}
              className="w-full mt-2 py-3.5 rounded-lg bg-primary text-primary-foreground font-semibold text-sm flex items-center justify-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed transition-all hover:glow-primary-strong"
            >
              <Search className="w-4 h-4" />
              {isSearching ? "Идёт поиск..." : "Найти путь"}
            </motion.button>
          </div>
        </motion.div>
      </motion.div>

      <AnimatePresence>
        {isSearching && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="relative z-10 mt-12"
          >
            <SearchLoader status={status} />
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {status === "done" && result?.path && (
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.6 }}
            className="relative z-10 mt-12 w-full max-w-3xl"
          >
            <PathTimeline result={result} />
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {errorText && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            className="relative z-10 mt-8 w-full max-w-2xl rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive"
          >
            {errorText}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default SearchPage;
