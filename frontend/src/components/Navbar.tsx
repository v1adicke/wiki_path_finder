import { useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { motion } from "framer-motion";
import { Search, BarChart3, Sun, Moon, Menu } from "lucide-react";
import { useTheme } from "@/hooks/use-theme";

export const Navbar = () => {
  const location = useLocation();
  const { theme, toggle } = useTheme();
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);

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

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (!menuRef.current?.contains(event.target as Node)) {
        setIsMenuOpen(false);
      }
    };

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsMenuOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleEscape);

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleEscape);
    };
  }, []);

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

      <div className="relative sm:hidden" ref={menuRef}>
        <button
          onClick={() => setIsMenuOpen((prev) => !prev)}
          className="p-1.5 rounded-md border border-border bg-secondary/30 text-muted-foreground hover:text-foreground transition-colors"
          aria-label="Open actions menu"
          aria-expanded={isMenuOpen}
          aria-haspopup="menu"
        >
          <Menu className="w-3.5 h-3.5" />
        </button>

        {isMenuOpen && (
          <div
            role="menu"
            className="absolute right-0 mt-2 w-44 rounded-lg border border-border bg-card/95 backdrop-blur-md shadow-lg p-1"
          >
            {socialLinks.map((social) => (
              <a
                key={social.href}
                href={social.href}
                target="_blank"
                rel="noopener noreferrer"
                role="menuitem"
                onClick={() => setIsMenuOpen(false)}
                className="flex items-center gap-2 px-2.5 py-2 rounded-md text-xs text-muted-foreground hover:text-foreground hover:bg-secondary/50 transition-colors"
              >
                <img
                  src={social.iconSrc}
                  alt={social.label}
                  className="w-3.5 h-3.5 opacity-80 dark:invert"
                />
                <span>{social.label}</span>
              </a>
            ))}

            <button
              onClick={() => {
                toggle();
                setIsMenuOpen(false);
              }}
              role="menuitem"
              className="w-full flex items-center gap-2 px-2.5 py-2 rounded-md text-xs text-muted-foreground hover:text-foreground hover:bg-secondary/50 transition-colors"
            >
              {theme === "dark" ? <Sun className="w-3.5 h-3.5" /> : <Moon className="w-3.5 h-3.5" />}
              <span>Смена темы</span>
            </button>
          </div>
        )}
      </div>

      <div className="hidden sm:flex items-center gap-3">
        {socialLinks.map((social) => (
          <a
            key={social.href}
            href={social.href}
            target="_blank"
            rel="noopener noreferrer"
            className="group p-1.5 rounded-md border border-border bg-secondary/30 text-muted-foreground hover:text-foreground hover:bg-secondary/50 transition-colors"
            aria-label={social.label}
            title={social.label}
          >
            <img
              src={social.iconSrc}
              alt={social.label}
              className="w-3.5 h-3.5 opacity-80 group-hover:opacity-100 dark:invert transition-opacity"
            />
          </a>
        ))}
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
