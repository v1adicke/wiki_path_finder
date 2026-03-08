import { motion } from "framer-motion";
import { SearchStatus } from "@/lib/api";

interface SearchLoaderProps {
  status: SearchStatus;
}

export const SearchLoader = ({ status }: SearchLoaderProps) => {
  const label = status === "heuristic" ? "Эвристический поиск..." : "Точный поиск...";
  const sublabel = status === "heuristic"
    ? "Быстрый проход с ограничением ветвления"
    : "Fallback без ограничений";

  return (
    <div className="flex flex-col items-center gap-6">
      <div className="relative w-20 h-20">
        <motion.div
          className="absolute inset-0 rounded-full border-2 border-primary/30"
          animate={{ scale: [1, 1.4, 1], opacity: [0.5, 0, 0.5] }}
          transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
        />
        <motion.div
          className="absolute inset-2 rounded-full border-2 border-primary/50"
          animate={{ scale: [1, 1.3, 1], opacity: [0.7, 0.1, 0.7] }}
          transition={{ duration: 2, repeat: Infinity, ease: "easeInOut", delay: 0.3 }}
        />
        <motion.div
          className="absolute inset-4 rounded-full border-2 border-primary"
          animate={{ rotate: 360 }}
          transition={{ duration: 3, repeat: Infinity, ease: "linear" }}
          style={{ borderTopColor: "transparent", borderRightColor: "transparent" }}
        />
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="w-2 h-2 rounded-full bg-primary animate-pulse-glow" />
        </div>
      </div>

      <div className="text-center">
        <motion.p
          key={status}
          initial={{ opacity: 0, y: 5 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-sm font-mono text-foreground"
        >
          {label}
        </motion.p>
        <p className="text-xs text-muted-foreground mt-1">{sublabel}</p>
      </div>
    </div>
  );
};
