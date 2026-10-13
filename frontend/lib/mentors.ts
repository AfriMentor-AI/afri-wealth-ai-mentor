// Per-mentor presentation data from the Stitch designs (W7 / W1 / M5).
// Names and ids still come from the backend (fetchPersonas); this table only
// supplies the look: accent colour, role line, quote, portraits.
export interface MentorMeta {
  id: string;
  name: string;
  role: string;
  /** short chip shown on the picker card and conversation rows */
  domain: string;
  focus: string;
  place: string;
  quote: string;
  quoteSource: string;
  /** Tailwind colour token suffix: persona-<accent> */
  accent: "market-queen" | "tech-founder" | "trader" | "rural-hustler" | "creative";
  avatar: string; // small round image key
  portrait: string; // arch portrait key
  starters: string[];
  welcome: string;
}

export const MENTORS: Record<string, MentorMeta> = {
  "market-queen": {
    id: "market-queen", name: "Chioma Okonjo", role: "The Market Queen", domain: "Retail liquidity",
    focus: "Balogun & Onitsha Retail FMCG • Working Capital Custodian", place: "Lagos • Onitsha",
    quote: "Cashflow is the pulse of the market; never let pride drain your working capital.", quoteSource: "Balogun Merchant Lore",
    accent: "market-queen", avatar: "i_3Tl309MwQZYxT3zm", portrait: "i_zJ52U2bpbGyajLc4",
    starters: ["🌾 Preparing for dry season stock", "💰 Reserve vs supplier 30% advance", "📊 Negotiating staged wholesale terms"],
    welcome: "Welcome back. Tell me what is moving in your market today, or what decision weighs on your mind.",
  },
  "tech-founder": {
    id: "tech-founder", name: "Faraji Mwangi", role: "The Tech Founder", domain: "Venture runway",
    focus: "Silicon Savannah & Cross-Border SaaS • Venture Runway", place: "Nairobi • Karen",
    quote: "Build lean, preserve equity, and treat cross-border liquidity as sovereign infrastructure.", quoteSource: "Savannah Scale Formula",
    accent: "tech-founder", avatar: "i_axaDAXUh6y8KPa43", portrait: "i_mPO2sLAu919yQqsm",
    starters: ["🚀 How long is my runway?", "🌍 Paying suppliers across borders", "🧾 Pricing my product for growth"],
    welcome: "Good to see you. Tell me where the company stands today, and what you need to decide next.",
  },
  trader: {
    id: "trader", name: "Alhaji Musa Haruna", role: "The Trader", domain: "Commodity arbitrage",
    focus: "Kano Commodity & Grain Arbitrage • Seasonal Reserve Patriarch", place: "Kano • Dawanau",
    quote: "He who buys grain before the rains secures the harvest for seven seasons.", quoteSource: "Dawanau Reserve Principle",
    accent: "trader", avatar: "i_bMQCTM2nzD5gCCOy", portrait: "i_JF7NUujrmG16Zx2M",
    starters: ["🌧️ Bulk buying before the rains", "📦 Holding stock or selling now", "🤝 Negotiating with a big buyer"],
    welcome: "Peace be with you. Tell me what you are buying, what you are selling, and what keeps you awake.",
  },
  "rural-hustler": {
    id: "rural-hustler", name: "Uwase Teddy", role: "The Rural Hustler", domain: "Communal credit",
    focus: "Sahelian Agritech & Cooperative Credit • Resilient Value Chains", place: "Kigali • Kicukiro",
    quote: "Group savings start small, but communal discipline outlasts foreign shocks.", quoteSource: "Tontine Stewardship Oath",
    accent: "rural-hustler", avatar: "i_DOa6N8ifgV1zLBZ0", portrait: "i_xwdAlX55pwvIxQSw",
    starters: ["👥 Starting a savings group", "🌱 Funding next season’s inputs", "📉 Surviving a bad harvest"],
    welcome: "Welcome, my friend. Tell me about your farm, your group, and the season ahead.",
  },
  creative: {
    id: "creative", name: "Kofi Boateng", role: "The Creative Sovereign", domain: "IP • media assets",
    focus: "Accra IP Licensing, Media Arts & Commission Cashflow", place: "Accra • Osu",
    quote: "Never surrender your masters; demand 50% upfront before the craft begins.", quoteSource: "Artisan Sovereignty Canon",
    accent: "creative", avatar: "i_fM1CD1UHbDkNndQW", portrait: "i_G1oqUrXpaogQwIoH",
    starters: ["🎨 Pricing a commission", "📝 Protecting my work", "💸 Smoothing irregular income"],
    welcome: "Hello, creator. Tell me what you are making, who is paying, and where the money gets stuck.",
  },
};

export const DEFAULT_MENTOR = MENTORS["market-queen"];

/** Persona ids from the backend may differ slightly; match by id, then by first name. */
export function mentorFor(p?: { id?: string; name?: string } | null): MentorMeta {
  if (!p) return DEFAULT_MENTOR;
  if (p.id && MENTORS[p.id]) return MENTORS[p.id];
  const first = (p.name || "").toLowerCase().split(/\s+/).filter((w) => w !== "alhaji")[0];
  const hit = Object.values(MENTORS).find((m) => m.name.toLowerCase().split(/\s+/).filter((w) => w !== "alhaji")[0] === first);
  return hit ?? DEFAULT_MENTOR;
}

export const ACCENT_RING: Record<MentorMeta["accent"], string> = {
  "market-queen": "ring-persona-market-queen",
  "tech-founder": "ring-persona-tech-founder",
  trader: "ring-persona-trader",
  "rural-hustler": "ring-persona-rural-hustler",
  creative: "ring-persona-creative",
};
export const ACCENT_TEXT: Record<MentorMeta["accent"], string> = {
  "market-queen": "text-persona-market-queen",
  "tech-founder": "text-persona-tech-founder",
  trader: "text-persona-trader",
  "rural-hustler": "text-persona-rural-hustler",
  creative: "text-persona-creative",
};
export const ACCENT_BG: Record<MentorMeta["accent"], string> = {
  "market-queen": "bg-persona-market-queen",
  "tech-founder": "bg-persona-tech-founder",
  trader: "bg-persona-trader",
  "rural-hustler": "bg-persona-rural-hustler",
  creative: "bg-persona-creative",
};
export const ACCENT_BORDER: Record<MentorMeta["accent"], string> = {
  "market-queen": "border-persona-market-queen",
  "tech-founder": "border-persona-tech-founder",
  trader: "border-persona-trader",
  "rural-hustler": "border-persona-rural-hustler",
  creative: "border-persona-creative",
};
