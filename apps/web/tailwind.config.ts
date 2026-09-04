import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        /* ── Charte : rôles sémantiques, définis dans globals.css ──────────
           Utiliser ces noms et jamais un hexadécimal. `hl` est LA couleur de
           mise en avant : elle bascule seule entre clair et sombre, ce qu'un
           `#1C6091` écrit en dur ne pouvait pas faire. */
        hl: {
          DEFAULT: "rgb(var(--hl-rgb) / <alpha-value>)",
          strong: "rgb(var(--hl-strong-rgb) / <alpha-value>)",
          soft: "rgb(var(--hl-soft-rgb) / <alpha-value>)",
          contrast: "rgb(var(--hl-contrast-rgb) / <alpha-value>)",
        },
        corten: {
          DEFAULT: "rgb(var(--accent-rgb) / <alpha-value>)",
          strong: "rgb(var(--accent-strong-rgb) / <alpha-value>)",
        },
        positive: "rgb(var(--positive-rgb) / <alpha-value>)",
        danger: "rgb(var(--danger-rgb) / <alpha-value>)",
        line: "rgb(var(--line-rgb) / <alpha-value>)",
        sunken: "rgb(var(--sunken-rgb) / <alpha-value>)",
        raised: "rgb(var(--raised-rgb) / <alpha-value>)",

        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        // Palette "Cyanotype & Chantier" — bleu de plan technique + ochre de
        // terrain. Remplace les namespaces morts `btp-*`/`tg-*` (0 usage
        // trouvé dans tout apps/web/src au 02/09) issus du template TailGrids
        // d'origine. Utilisée directement via ces tokens nommés pour tout
        // nouveau composant ; les fichiers existants référencent surtout les
        // valeurs hex équivalentes en dur (voir globals.css) pour l'instant.
        blueprint: {
          950: "#0A121A",
          900: "#111A24",
          800: "#16212D",
          700: "#243546",
          600: "#1C6091",
          500: "#2B75AB",
          400: "#4F9BC7",
          300: "#6BAAD4",
          100: "#EAF1F5",
        },
        ochre: {
          700: "#824512",
          600: "#9C5518",
          500: "#B5651D",
          400: "#C97A2E",
          300: "#E0A264",
        },
        signal: {
          600: "#2C6B4C",
          500: "#3D8B67",
          400: "#7FC7A4",
        },
      },
      borderRadius: {
        '2xl': "12px",
        xl: "8px",
        lg: "6px",
        md: "5px",
        sm: "4px",
      },
      fontFamily: {
        sans: ["var(--font-jakarta)", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "sans-serif"],
        heading: ["var(--font-archivo)", "var(--font-jakarta)", "-apple-system", "sans-serif"],
        mono: ["var(--font-jetbrains-mono)", "JetBrains Mono", "monospace"],
      },
      boxShadow: {
        'xs': '0 1px 2px 0 rgba(10, 18, 26, 0.05)',
        'sm': '0 1px 3px 0 rgba(10, 18, 26, 0.07), 0 1px 2px -1px rgba(10, 18, 26, 0.07)',
        'subtle': '0 1px 2px 0 rgba(10, 18, 26, 0.04)',
        'elevated': '0 4px 12px -2px rgba(10, 18, 26, 0.08), 0 1px 3px -1px rgba(10, 18, 26, 0.05)',
        'floating': '0 12px 40px -8px rgba(10, 18, 26, 0.16), 0 4px 12px -4px rgba(10, 18, 26, 0.08)',
        'glass': '0 8px 32px -4px rgba(10, 18, 26, 0.1), 0 2px 8px -2px rgba(10, 18, 26, 0.05)',
        'glow-blueprint': '0 0 24px -6px rgba(28, 96, 145, 0.25)',
        'glow-ochre': '0 0 24px -6px rgba(181, 101, 29, 0.25)',
        'inner-glow': 'inset 0 1px 0 0 rgba(255, 255, 255, 0.04)',
      },
      animation: {
        'fade-in-up': 'fade-in-up 0.3s ease-out both',
        'scale-in': 'scale-in 0.2s ease-out both',
        'slide-in-right': 'slide-in-right 0.25s ease-out both',
      },
      keyframes: {
        'fade-in-up': {
          from: { opacity: '0', transform: 'translateY(8px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'scale-in': {
          from: { opacity: '0', transform: 'scale(0.96)' },
          to: { opacity: '1', transform: 'scale(1)' },
        },
        'slide-in-right': {
          from: { opacity: '0', transform: 'translateX(12px)' },
          to: { opacity: '1', transform: 'translateX(0)' },
        },
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;
