'use client';

import React, { createContext, useContext, useEffect, useState } from 'react';

export type Theme = 'light' | 'dark' | 'system' | 'schedule';
export type ResolvedTheme = 'light' | 'dark';

interface ThemeContextType {
  theme: Theme;
  resolvedTheme: ResolvedTheme;
  setTheme: (theme: Theme) => void;
}

const ThemeContext = createContext<ThemeContextType>({
  theme: 'system',
  resolvedTheme: 'light',
  setTheme: () => {},
});

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<Theme>('system');
  const [resolvedTheme, setResolvedTheme] = useState<ResolvedTheme>('light');
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const saved = (localStorage.getItem('btp_theme') as Theme) || 'system';
    setThemeState(saved);
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!mounted) return;

    function isBusinessDaytime() {
      const now = new Date();
      const currentHours = now.getHours() + now.getMinutes() / 60;
      // Daytime clarity: 07:30 to 20:30 (avoids switching dark too early at 17h/18h)
      return currentHours >= 7.5 && currentHours < 20.5;
    }

    function applyTheme() {
      let active: ResolvedTheme = 'light';

      if (theme === 'light') {
        active = 'light';
      } else if (theme === 'dark') {
        active = 'dark';
      } else if (theme === 'schedule') {
        // Scheduled mode: 07:30 to 20:30 Light, 20:30 to 07:30 Dark
        active = isBusinessDaytime() ? 'light' : 'dark';
      } else {
        // 'system' mode: Follows OS preference
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        active = prefersDark ? 'dark' : 'light';
      }

      setResolvedTheme(active);
      const root = document.documentElement;
      if (active === 'dark') {
        root.classList.add('dark');
        root.classList.remove('light');
      } else {
        root.classList.add('light');
        root.classList.remove('dark');
      }
    }

    applyTheme();
    localStorage.setItem('btp_theme', theme);

    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const listener = () => applyTheme();
    mediaQuery.addEventListener('change', listener);

    // Periodic time check every 2 minutes for smooth schedule transitions
    const interval = setInterval(() => {
      if (theme === 'schedule') {
        applyTheme();
      }
    }, 2 * 60 * 1000);

    return () => {
      mediaQuery.removeEventListener('change', listener);
      clearInterval(interval);
    };
  }, [theme, mounted]);

  return (
    <ThemeContext.Provider value={{ theme, resolvedTheme, setTheme: setThemeState }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}
