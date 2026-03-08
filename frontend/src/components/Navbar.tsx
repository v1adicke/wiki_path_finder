import { Link, useLocation } from "react-router-dom";
import { motion } from "framer-motion";
import { Search, BarChart3, Sun, Moon } from "lucide-react";
import { useTheme } from "@/hooks/use-theme";

export const Navbar = () => {
  const location = useLocation();
  const { theme, toggle } = useTheme();

  const links = [
    { to: "/", label: "Поиск", icon: Search },
    { to: "/dashboard", label: "Бенчмарки", icon: BarChart3 },
  ];

  return (
    <motion.nav
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-6 py-4 bg-background/80 backdrop-blur-md border-b border-border/50"
    >
      <Link to="/" className="flex items-center gap-2">
        <img
          src="/favicon.svg"
          alt="WikiPath logo"
          className="w-6 h-6 dark:invert"
        />
        <span className="font-semibold text-sm text-foreground">WikiPath</span>
      </Link>

      <div className="flex items-center gap-1 rounded-lg border border-border bg-secondary/30 p-1">
        {links.map((link) => {
          const isActive = location.pathname === link.to;
          return (
            <Link
              key={link.to}
              to={link.to}
              className={`relative flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                isActive ? "text-foreground" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {isActive && (
                <motion.div
                  layoutId="nav-active"
                  className="absolute inset-0 bg-secondary rounded-md"
                  transition={{ type: "spring", duration: 0.4 }}
                />
              )}
              <link.icon className="relative z-10 w-3.5 h-3.5" />
              <span className="relative z-10">{link.label}</span>
            </Link>
          );
        })}
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={toggle}
          className="p-1.5 rounded-md border border-border bg-secondary/30 text-muted-foreground hover:text-foreground transition-colors"
          aria-label="Toggle theme"
        >
          {theme === "dark" ? <Sun className="w-3.5 h-3.5" /> : <Moon className="w-3.5 h-3.5" />}
        </button>
      </div>
    </motion.nav>
  );
};
