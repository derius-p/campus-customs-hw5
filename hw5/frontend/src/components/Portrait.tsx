// Friendly cartoon portraits of the Yale officers who stand in for each agent on the board.
// Drawn from scratch in SVG (no photos are stored or shipped); features follow each person's
// official Yale headshot: hair, coloring, glasses, earrings, and what they wear.
import { useId } from "react";
import type { AgentName } from "../types";

type Look = {
  skin: string;
  skinShade: string;
  hair: string;
  hairShade: string;
  style: "long-wavy" | "shoulder" | "bald" | "short";
  jacket: string;
  shirt: string;
  tie?: { color: string; dots?: string };
  glasses?: boolean;
  earrings?: "studs" | "hoops";
  necklace?: boolean;
  smile: "big" | "soft";
};

const LOOKS: Record<AgentName, Look> = {
  // Maurie McInnis: long wavy blonde hair, navy blazer, white top, gold chain and earrings
  boss: {
    skin: "#f7d9c6", skinShade: "#e9bfa6", hair: "#ecc97c", hairShade: "#d3aa59", style: "long-wavy",
    jacket: "#1d2a4d", shirt: "#ffffff", earrings: "studs", necklace: true, smile: "big",
  },
  // Geoffrey Chatas: bald, rosy, navy suit, light blue shirt, navy tie with gold dots
  inventory: {
    skin: "#f3c9b1", skinShade: "#e2ab90", hair: "#b8a18a", hairShade: "#9d8670", style: "bald",
    jacket: "#22386b", shirt: "#cfe0f3", tie: { color: "#1b2752", dots: "#f2c94c" }, smile: "big",
  },
  // Katrina Spencer: shoulder-length honey hair with a side part, gold hoops, dark top
  accounting: {
    skin: "#f4d0b8", skinShade: "#e5b498", hair: "#c4955a", hairShade: "#a77a43", style: "shoulder",
    jacket: "#1f2b45", shirt: "#2f3d5c", earrings: "hoops", smile: "big",
  },
  // Mike Bellamy: close-cropped gray hair, black glasses, navy suit, white shirt, blue tie
  facilities: {
    skin: "#7b4c33", skinShade: "#653c27", hair: "#5a5a5a", hairShade: "#3d3d3d", style: "short",
    jacket: "#1e2840", shirt: "#ffffff", tie: { color: "#3f6fc4", dots: "#8fb0e6" }, glasses: true, smile: "soft",
  },
  // Renee Kopkowski: shoulder-length auburn hair, navy blazer, teal blouse
  customer_service: {
    skin: "#f6d5c2", skinShade: "#e8b9a1", hair: "#8e412b", hairShade: "#6f2f1e", style: "shoulder",
    jacket: "#1d2a45", shirt: "#1f8a8a", smile: "big",
  },
};

export default function Portrait({ agent, size = 56, ring }: { agent: AgentName; size?: number; ring?: string }) {
  const L = LOOKS[agent];
  const clip = useId().replace(/:/g, "");
  return (
    <svg className="portrait" width={size} height={size} viewBox="0 0 120 120" aria-hidden="true">
      <defs>
        <clipPath id={clip}>
          <circle cx="60" cy="60" r="58" />
        </clipPath>
      </defs>
      <circle cx="60" cy="60" r="59" fill={ring ?? "#d9e7f7"} />
      <g clipPath={`url(#${clip})`}>
        <circle cx="60" cy="60" r="56" fill="#f4f1ea" />

        {/* hair that falls behind the head and shoulders */}
        {L.style === "long-wavy" && (
          <path
            d="M33 52 C28 22 92 22 87 52 C91 66 96 80 92 92 C95 100 90 108 84 110 L36 110 C30 108 25 100 28 92 C24 80 29 66 33 52 Z"
            fill={L.hair}
          />
        )}
        {L.style === "shoulder" && (
          <path d="M34 50 C31 22 89 22 86 50 L89 82 C90 90 84 94 78 92 L42 92 C36 94 30 90 31 82 Z" fill={L.hair} />
        )}

        {/* shoulders: jacket, shirt, lapels */}
        <path d="M8 124 C12 100 32 90 60 90 C88 90 108 100 112 124 Z" fill={L.jacket} />
        <path d="M49 90 L71 90 L60 112 Z" fill={L.shirt} />
        <path d="M49 90 L60 112 L52 124 L42 96 Z" fill="rgba(255,255,255,0.08)" />
        <path d="M71 90 L60 112 L68 124 L78 96 Z" fill="rgba(0,0,0,0.12)" />
        {L.tie && (
          <g>
            <path d="M57 92 L63 92 L62 97 L58 97 Z" fill={L.tie.color} />
            <path d="M58 97 L62 97 L65 114 L60 120 L55 114 Z" fill={L.tie.color} />
            {L.tie.dots && (
              <g fill={L.tie.dots}>
                <circle cx="59" cy="102" r="0.9" />
                <circle cx="61.5" cy="107" r="0.9" />
                <circle cx="58.5" cy="112" r="0.9" />
                <circle cx="61" cy="116" r="0.9" />
              </g>
            )}
          </g>
        )}

        {/* neck and head */}
        <path d="M51 74 L69 74 L70 92 Q60 98 50 92 Z" fill={L.skinShade} />
        {L.necklace && (
          <path d="M49 91 Q60 104 71 91" fill="none" stroke="#d4a437" strokeWidth="1.8" strokeDasharray="1.6 1.2" />
        )}
        <ellipse cx="38.5" cy="56" rx="4" ry="6" fill={L.skinShade} />
        <ellipse cx="81.5" cy="56" rx="4" ry="6" fill={L.skinShade} />
        <ellipse cx="60" cy="53" rx="22" ry="25.5" fill={L.skin} />

        {/* hair on top of the head */}
        {(L.style === "long-wavy" || L.style === "shoulder") && (
          <path
            d="M37 50 C35 27 54 21 66 25 C79 28 86 39 83 53 C79 42 72 35 63 33 C55 37 45 41 37 50 Z"
            fill={L.hair}
          />
        )}
        {(L.style === "long-wavy" || L.style === "shoulder") && (
          <path d="M63 33 C70 34 77 40 80 47" fill="none" stroke={L.hairShade} strokeWidth="1.2" strokeLinecap="round" />
        )}
        {L.style === "short" && (
          <path d="M38.5 47 C37 27 83 27 81.5 47 C79 38 71 32.5 60 32.5 C49 32.5 41 38 38.5 47 Z" fill={L.hair} />
        )}
        {L.style === "bald" && (
          <g fill={L.hair}>
            <path d="M38 50 C38 44 40 41 42 40 L43 56 C41 56 38 54 38 50 Z" />
            <path d="M82 50 C82 44 80 41 78 40 L77 56 C79 56 82 54 82 50 Z" />
          </g>
        )}
        {L.style === "bald" && <ellipse cx="52" cy="35" rx="7" ry="3.5" fill="#ffffff" opacity="0.35" />}

        {/* face */}
        <path d="M47.5 46 Q51.5 43.5 55.5 46" fill="none" stroke={L.style === "bald" ? "#8d7058" : L.hairShade} strokeWidth="1.8" strokeLinecap="round" />
        <path d="M64.5 46 Q68.5 43.5 72.5 46" fill="none" stroke={L.style === "bald" ? "#8d7058" : L.hairShade} strokeWidth="1.8" strokeLinecap="round" />
        <ellipse cx="51.5" cy="52" rx="2.3" ry={L.smile === "big" ? 2.1 : 2.4} fill="#2b2b33" />
        <ellipse cx="68.5" cy="52" rx="2.3" ry={L.smile === "big" ? 2.1 : 2.4} fill="#2b2b33" />
        <circle cx="52.3" cy="51.2" r="0.7" fill="#fff" />
        <circle cx="69.3" cy="51.2" r="0.7" fill="#fff" />
        <path d="M59 54 Q57 60 60 61.5" fill="none" stroke={L.skinShade} strokeWidth="1.6" strokeLinecap="round" />
        {L.smile === "big" ? (
          <>
            <circle cx="45" cy="62" r="3.6" fill="#f08c8c" opacity="0.28" />
            <circle cx="75" cy="62" r="3.6" fill="#f08c8c" opacity="0.28" />
            <path d="M51 65 Q60 75 69 65 Z" fill="#ffffff" stroke="#9b4545" strokeWidth="1.4" strokeLinejoin="round" />
          </>
        ) : (
          <path d="M54 67 Q60 69.5 66 67" fill="none" stroke="#3a2318" strokeWidth="1.6" strokeLinecap="round" />
        )}
        {L.glasses && (
          <g fill="none" stroke="#141414" strokeWidth="2">
            <rect x="44" y="47" width="14" height="10" rx="3.5" />
            <rect x="62" y="47" width="14" height="10" rx="3.5" />
            <path d="M58 51 Q60 49.5 62 51" />
            <path d="M44 50 L39.5 49" />
            <path d="M76 50 L80.5 49" />
          </g>
        )}
        {L.earrings === "studs" && (
          <g fill="#d4a437">
            <circle cx="38.5" cy="61.5" r="1.6" />
            <circle cx="81.5" cy="61.5" r="1.6" />
          </g>
        )}
        {L.earrings === "hoops" && (
          <g fill="none" stroke="#d4a437" strokeWidth="1.4">
            <circle cx="38" cy="65" r="3.6" />
            <circle cx="82" cy="65" r="3.6" />
          </g>
        )}
      </g>
    </svg>
  );
}
