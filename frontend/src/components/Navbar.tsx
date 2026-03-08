import { Link, useLocation } from "react-router-dom";
import { motion } from "framer-motion";
import { Search, BarChart3, Sun, Moon } from "lucide-react";
import { useTheme } from "@/hooks/use-theme";

export const Navbar = () => {
  const location = useLocation();
  const { theme, toggle } = useTheme();

  const socialLinks = [
    {
      href: "https://github.com/v1adicke/wiki_path_finder",
      label: "GitHub",
      iconSrc: "/icons/social/github.svg",
    },
    {
      href: "https://t.me/wikipathfinder_bot",
      label: "Telegram",
      iconSrc: "/icons/social/telegram.svg",
    },
  ];

  const links = [
    { to: "/", label: "Поиск", icon: Search },
    { to: "/dashboard", label: "Бенчмарки", icon: BarChart3 },
  ];

  return (
    <motion.nav
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between gap-2 px-3 py-2 sm:px-6 sm:py-4 bg-background/80 backdrop-blur-md border-b border-border/50"
    >
      <Link to="/" className="flex items-center gap-2">
        <img
          src="/favicon.svg"
          alt="WikiPath logo"
          className="w-5 h-5 sm:w-6 sm:h-6 dark:invert"
        />
        <span className="hidden sm:inline font-semibold text-sm text-foreground">WikiPath</span>
      </Link>

      <div className="flex items-center gap-0.5 rounded-lg border border-border bg-secondary/30 p-0.5 sm:gap-1 sm:p-1">
        {links.map((link) => {
          const isActive = location.pathname === link.to;
          return (
            <Link
              key={link.to}
              to={link.to}
              aria-label={link.label}
              className={`relative flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium transition-colors sm:gap-1.5 sm:px-3 sm:py-1.5 ${
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
              <span className="relative z-10 hidden md:inline">{link.label}</span>
            </Link>
          );
        })}
      </div>

      <div className="flex items-center gap-1 sm:gap-2 md:gap-3">
        {socialLinks.map((social) => (
          <a
            key={social.href}
            href={social.href}
            target="_blank"
            rel="noopener noreferrer"
            className="group p-1 rounded-md border border-border bg-secondary/30 text-muted-foreground hover:text-foreground hover:bg-secondary/50 transition-colors sm:p-1.5"
            aria-label={social.label}
            title={social.label}
          >
            <img
              src={social.iconSrc}
              alt={social.label}
              className="w-3 h-3 sm:w-3.5 sm:h-3.5 opacity-80 group-hover:opacity-100 dark:invert transition-opacity"
            />
          </a>
        ))}
        <button
          onClick={toggle}
          className="p-1 rounded-md border border-border bg-secondary/30 text-muted-foreground hover:text-foreground transition-colors sm:p-1.5"
          aria-label="Toggle theme"
        >
          {theme === "dark" ? <Sun className="w-3 h-3 sm:w-3.5 sm:h-3.5" /> : <Moon className="w-3 h-3 sm:w-3.5 sm:h-3.5" />}
        </button>
      </div>
    </motion.nav>
  );
};
