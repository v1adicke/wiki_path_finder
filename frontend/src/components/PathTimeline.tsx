import { motion } from "framer-motion";
import { ExternalLink, Clock, CheckCircle2 } from "lucide-react";
import { SearchResult } from "@/lib/api";

interface PathTimelineProps {
  result: SearchResult;
}

export const PathTimeline = ({ result }: PathTimelineProps) => {
  if (!result.path) return null;

  return (
    <div className="space-y-6">
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.2 }}
        className="flex items-center justify-center gap-6 text-sm"
      >
        <div className="flex items-center gap-2 text-primary">
          <CheckCircle2 className="w-4 h-4" />
          <span className="font-mono">Путь найден</span>
        </div>
        <div className="flex items-center gap-2 text-muted-foreground">
          <Clock className="w-4 h-4" />
          <span className="font-mono">{result.elapsed_time.toFixed(2)} сек</span>
        </div>
        <div className="text-muted-foreground font-mono">
          {result.steps_count} {result.steps_count === 1 ? "шаг" : result.steps_count < 5 ? "шага" : "шагов"}
        </div>
      </motion.div>

      <div className="flex items-center justify-center flex-wrap gap-0">
        {result.path.map((article, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.3 + i * 0.15, duration: 0.4 }}
            className="flex items-center"
          >
            <a
              href={`https://ru.wikipedia.org/wiki/${encodeURIComponent(article)}`}
              target="_blank"
              rel="noopener noreferrer"
              className="group relative px-4 py-3 rounded-xl border border-border bg-card hover:border-primary/40 hover:glow-primary transition-all"
            >
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-foreground group-hover:text-primary transition-colors">
                  {article}
                </span>
                <ExternalLink className="w-3 h-3 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
              </div>
              <span className="absolute -top-2.5 left-3 px-1.5 py-0.5 text-[10px] font-mono bg-background text-muted-foreground border border-border rounded">
                {i + 1}
              </span>
            </a>

            {i < result.path!.length - 1 && (
              <motion.div
                initial={{ scaleX: 0 }}
                animate={{ scaleX: 1 }}
                transition={{ delay: 0.4 + i * 0.15, duration: 0.3 }}
                className="w-8 h-px bg-primary/40 mx-1 origin-left"
              />
            )}
          </motion.div>
        ))}
      </div>
    </div>
  );
};
