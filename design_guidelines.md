{
  "design_system_name": "Rahaza APS (Phase 19) — Galaxy Glass Scheduling",
  "product_context": {
    "app_type": "dashboard",
    "audience": "Manajer produksi & supervisor pabrik garmen (desktop-first, data-dense)",
    "primary_jobs": [
      "Melihat jadwal WO per line secara cepat (Gantt)",
      "Mendeteksi risiko: overdue / at-risk / overload kapasitas",
      "Reschedule WO (klik bar → panel detail → ubah tanggal)",
      "Menjalankan Auto-Schedule dan review preview sebelum commit"
    ],
    "success_actions": [
      "Scroll/zoom timeline tetap 60fps pada 100+ WO",
      "Overload terlihat jelas via heatmap + badge",
      "Reschedule tidak ambigu (before/after jelas)",
      "Semua aksi penting punya data-testid"
    ],
    "language": "id-ID",
    "must_preserve": [
      "Glass dark UI existing (var(--glass-bg), GlassCard/GlassPanel)",
      "Semantic accents emerald/amber/red",
      "ThemeToggle (dark/light/classic) tetap kompatibel"
    ]
  },

  "visual_personality": {
    "keywords": ["glass-dark", "industrial-precise", "dense-but-readable", "status-forward", "calm-glow"],
    "layout_principles": [
      "Sticky left column untuk nama line + KPI mini",
      "Timeline grid seperti ‘engineering chart’ (hairline + subtle glow)",
      "Bento KPI strip di atas (4–6 tiles) untuk scanning cepat",
      "Detail muncul sebagai side-panel (Sheet/Drawer) agar konteks timeline tidak hilang"
    ],
    "do_not": [
      "Jangan ubah token global di index.css (cukup extend via class lokal APS)",
      "Jangan pakai gradient besar (maks 20% viewport) dan jangan gradient gelap/saturated",
      "Jangan pakai transition: all"
    ]
  },

  "typography": {
    "fonts": {
      "current": {
        "display": "Inter",
        "ui": "Inter",
        "mono": "JetBrains Mono"
      },
      "aps_override_optional": {
        "goal": "Meningkatkan keterbacaan angka/tanggal di timeline tanpa ganti global font",
        "recommendation": "Gunakan font-mono (JetBrains Mono) untuk header tanggal, tick marks, dan angka kapasitas; tetap Inter untuk label/teks."
      }
    },
    "scale": {
      "h1": "text-4xl sm:text-5xl lg:text-6xl (dipakai hanya untuk page header besar; APS biasanya cukup text-2xl)",
      "page_title": "text-2xl font-bold",
      "section_title": "text-sm font-semibold",
      "body": "text-sm (desktop), text-xs (dense table/legend)",
      "micro": "text-[10px] untuk chip/axis labels"
    },
    "number_format": {
      "locale": "id-ID",
      "rules": [
        "Tanggal: gunakan format singkat di header timeline (mis. 12 Jan)",
        "Angka kapasitas: tampilkan % bulat + tooltip detail (mis. 132% → 'Overload 32%')"
      ]
    }
  },

  "color_system": {
    "source_of_truth": "Gunakan token HSL shadcn + CSS vars yang sudah ada di /app/frontend/src/index.css",
    "semantic": {
      "status": {
        "draft": {
          "label": "Draft",
          "bar_bg": "bg-foreground/10",
          "bar_border": "border-foreground/15",
          "text": "text-muted-foreground"
        },
        "released": {
          "label": "Released",
          "bar_bg": "bg-sky-400/15",
          "bar_border": "border-sky-400/25",
          "text": "text-sky-300"
        },
        "in_production": {
          "label": "Produksi",
          "bar_bg": "bg-emerald-400/15",
          "bar_border": "border-emerald-400/25",
          "text": "text-emerald-300"
        },
        "completed": {
          "label": "Selesai",
          "bar_bg": "bg-emerald-500/10",
          "bar_border": "border-emerald-400/15",
          "text": "text-emerald-200"
        }
      },
      "risk": {
        "on_track": {
          "stroke": "ring-emerald-400/40",
          "chip": "bg-emerald-500/15 text-emerald-300 border-emerald-400/25"
        },
        "at_risk": {
          "stroke": "ring-amber-400/45",
          "chip": "bg-amber-500/15 text-amber-300 border-amber-400/25"
        },
        "overdue": {
          "stroke": "ring-red-400/50",
          "chip": "bg-red-500/15 text-red-300 border-red-400/25"
        }
      },
      "capacity_heatmap": {
        "under_70": "bg-emerald-400/18",
        "70_90": "bg-sky-400/16",
        "90_110": "bg-amber-400/18",
        "over_110": "bg-red-400/18"
      }
    },
    "aps_local_tokens": {
      "note": "Tambahkan sebagai CSS vars scoped ke container APS (mis. .aps-root) bila perlu, tanpa mengubah :root.",
      "vars": {
        "--aps-grid-line": "rgba(255,255,255,0.07)",
        "--aps-grid-line-strong": "rgba(255,255,255,0.12)",
        "--aps-now-line": "rgba(47,183,255,0.65)",
        "--aps-selection": "rgba(79,124,255,0.18)",
        "--aps-bar-shadow": "0 10px 24px rgba(0,0,0,0.35)",
        "--aps-bar-shadow-hover": "0 0 0 1px rgba(79,124,255,0.18), 0 0 22px rgba(79,124,255,0.18)"
      }
    }
  },

  "layout_and_grid": {
    "page_shell": {
      "structure": [
        "Header: judul + KPI strip + actions (Auto-Schedule)",
        "Toolbar: filter/search + zoom toggle + legend",
        "Main: Gantt viewport (sticky left column + scrollable timeline)",
        "Right: side-panel detail (Sheet)"
      ],
      "max_width": "Gunakan full-width (monitor). Jangan center container.",
      "spacing": {
        "outer": "p-4 sm:p-6",
        "section_gap": "space-y-4 sm:space-y-6",
        "dense_controls": "gap-2"
      }
    },
    "gantt_geometry": {
      "row_height": "h-14 (line row) + heatmap strip h-6 di bawahnya",
      "left_sticky_col": {
        "width": "w-[260px] lg:w-[320px]",
        "content": ["Kode line + nama", "mini KPI: load hari ini, WIP count"],
        "style": "bg-[var(--card-surface)]/90 backdrop-blur border-r border-[var(--glass-border)]"
      },
      "timeline": {
        "min_column_width": {
          "day": "w-[56px]",
          "week": "w-[84px]",
          "month": "w-[120px]"
        },
        "header_height": "h-12 (sticky)",
        "grid": "hairline verticals + subtle weekend shading",
        "now_indicator": "1px line + small label 'Hari ini'"
      }
    }
  },

  "components": {
    "component_path": {
      "glass": "/app/frontend/src/components/ui/glass.jsx",
      "button": "/app/frontend/src/components/ui/button.jsx",
      "badge": "/app/frontend/src/components/ui/badge.jsx",
      "tabs": "/app/frontend/src/components/ui/tabs.jsx",
      "tooltip": "/app/frontend/src/components/ui/tooltip.jsx",
      "scroll_area": "/app/frontend/src/components/ui/scroll-area.jsx",
      "sheet": "/app/frontend/src/components/ui/sheet.jsx",
      "dialog": "/app/frontend/src/components/ui/dialog.jsx",
      "select": "/app/frontend/src/components/ui/select.jsx",
      "popover": "/app/frontend/src/components/ui/popover.jsx",
      "command": "/app/frontend/src/components/ui/command.jsx",
      "separator": "/app/frontend/src/components/ui/separator.jsx",
      "slider": "/app/frontend/src/components/ui/slider.jsx",
      "switch": "/app/frontend/src/components/ui/switch.jsx",
      "table": "/app/frontend/src/components/ui/table.jsx",
      "skeleton": "/app/frontend/src/components/ui/skeleton.jsx",
      "sonner": "/app/frontend/src/components/ui/sonner.jsx"
    },
    "aps_specific_building_blocks": {
      "kpi_strip": {
        "use": "GlassCard grid 4–6 tiles",
        "tile_pattern": "angka besar + label kecil + icon badge",
        "tailwind": "grid grid-cols-2 md:grid-cols-4 xl:grid-cols-6 gap-3"
      },
      "toolbar": {
        "use": "GlassPanel",
        "content": [
          "Search input (GlassInput)",
          "Filter status (Select)",
          "Filter prioritas (Select)",
          "Zoom toggle (ToggleGroup)",
          "Auto-Schedule button (Button primary)"
        ]
      },
      "legend": {
        "use": "Badge + small swatches",
        "placement": "kanan toolbar (desktop), collapsible (mobile)"
      },
      "gantt_viewport": {
        "use": "ScrollArea untuk horizontal + vertical (nested) atau 1 scroll container dengan sticky header/col",
        "note": "Untuk perf, hindari blur per-cell; blur hanya wrapper GlassPanel."
      },
      "work_order_bar": {
        "structure": [
          "Outer: absolute positioned div (left/width based on date)",
          "Inner: progress overlay (width = progress%)",
          "Right edge: resize handle (future)"
        ],
        "states": {
          "default": "border + bg status",
          "hover": "shadow + slight lift",
          "selected": "ring 2px + brighter border",
          "dragging": "opacity-80 + cursor-grabbing"
        }
      },
      "detail_panel": {
        "use": "Sheet (right side)",
        "sections": [
          "Header: WO code + status badge + risk chip",
          "Ringkasan: model, qty, SMV estimasi, line, tanggal",
          "Progress: Progress component",
          "Aksi: tombol 'Ubah Jadwal' (Dialog) + 'Kunci Jadwal' (Switch)"
        ]
      },
      "auto_schedule_preview": {
        "use": "Dialog (wide) + Table + mini charts (Recharts) untuk before/after load",
        "layout": "2 kolom: Before vs After, dengan delta badges",
        "confirm": "Button primary 'Terapkan Jadwal' + secondary 'Batal'"
      }
    }
  },

  "interaction_and_motion": {
    "principles": [
      "Micro-interactions wajib: hover, pressed, focus-visible jelas",
      "Scrolling timeline harus terasa ‘native’ (no heavy shadows per tick)",
      "Gunakan framer-motion hanya untuk panel masuk/keluar & bar hover highlight (bukan untuk 100+ bars)"
    ],
    "recommended_motion": {
      "side_panel": "framer-motion slide-in dari kanan (dur-2/3, ease-out)",
      "bar_hover": "transition-[box-shadow,transform,background-color,border-color] duration-200",
      "zoom_change": "animate header tick opacity (150ms) + keep scroll position anchored",
      "loading": "Skeleton untuk rows + shimmer halus (hindari animasi berat)"
    },
    "no_go": [
      "Jangan animasikan left/width bar saat scroll (perf)",
      "Jangan gunakan transition-all"
    ]
  },

  "data_dense_readability_rules": {
    "timeline_grid": [
      "Gunakan garis grid tipis (var --aps-grid-line) dan garis kuat tiap minggu/bulan",
      "Weekend shading: bg-foreground/5 (subtle) agar tidak mengganggu"
    ],
    "labels": [
      "WO bar label: tampilkan kode WO + qty singkat (mis. 'WO-1023 · 2.4k')",
      "Jika bar terlalu pendek: tampilkan tooltip saja (Tooltip shadcn)"
    ],
    "tooltips": {
      "content": ["Tanggal mulai/selesai", "SMV estimasi", "Load impact", "Status + risiko"],
      "style": "bg-[var(--popover-surface)] border border-[var(--glass-border)] text-xs"
    }
  },

  "accessibility": {
    "contrast": [
      "Pastikan teks utama pakai text-foreground, teks sekunder text-muted-foreground",
      "Chip status gunakan kombinasi bg/ border transparan seperti modul Andon"
    ],
    "keyboard": [
      "Tab order: toolbar → timeline bars (roving tabindex) → side panel",
      "Enter/Space pada bar membuka detail panel",
      "Esc menutup Sheet/Dialog"
    ],
    "reduced_motion": "Hormati prefers-reduced-motion (sudah ada global override).",
    "aria": [
      "Bar WO: role='button' + aria-label ringkas",
      "Heatmap cell: aria-label 'Line A, 12 Jan, load 132% (overload)'"
    ]
  },

  "testing_attributes": {
    "rule": "Semua elemen interaktif & info penting wajib data-testid (kebab-case).",
    "required_testids": [
      "aps-page",
      "aps-kpi-total-wo",
      "aps-kpi-overdue",
      "aps-kpi-at-risk",
      "aps-kpi-load-avg",
      "aps-toolbar-search-input",
      "aps-toolbar-status-select",
      "aps-toolbar-priority-select",
      "aps-toolbar-model-select",
      "aps-toolbar-zoom-toggle-day",
      "aps-toolbar-zoom-toggle-week",
      "aps-toolbar-zoom-toggle-month",
      "aps-auto-schedule-button",
      "aps-legend",
      "aps-gantt-scroll-container",
      "aps-gantt-sticky-line-column",
      "aps-gantt-timeline-header",
      "aps-now-indicator",
      "aps-line-row-{lineId}",
      "aps-wo-bar-{woId}",
      "aps-wo-tooltip-{woId}",
      "aps-capacity-cell-{lineId}-{yyyyMMdd}",
      "aps-detail-sheet",
      "aps-detail-reschedule-button",
      "aps-reschedule-dialog",
      "aps-auto-schedule-preview-dialog",
      "aps-auto-schedule-confirm-button"
    ]
  },

  "implementation_notes_for_main_agent": {
    "instructions_to_main_agent": [
      "Pertahankan GlassCard/GlassPanel dari /components/ui/glass.jsx sebagai wrapper utama APS.",
      "Bangun Gantt custom: gunakan 1 scroll container utama (overflow-auto) dengan sticky header (top:0) dan sticky left column (left:0).",
      "Untuk 60fps: render bars sebagai absolutely-positioned div di dalam row container; minimalkan DOM nodes per tick. Hindari blur per-cell.",
      "Zoom Day/Week/Month: ubah pxPerDay dan re-calc left/width; pertahankan scrollLeft anchor (tanggal di tengah viewport).",
      "Heatmap: render sebagai 1 strip per line (flex) dengan cell width = pxPerDay; gunakan Tooltip untuk detail.",
      "Reschedule MVP: klik bar → buka Sheet detail; tombol 'Ubah Jadwal' membuka Dialog dengan 2 input tanggal (type=date) + validasi.",
      "Auto-Schedule: tombol memanggil endpoint; tampilkan Dialog preview before/after (Table + Recharts mini bar). Commit hanya setelah confirm.",
      "Semua label/copy gunakan Bahasa Indonesia (contoh: 'Muat Ulang', 'Terapkan Jadwal', 'Pratinjau').",
      "Tambahkan data-testid pada semua kontrol sesuai daftar."
    ],
    "performance_scaffolds": {
      "react": [
        "Gunakan memoization (useMemo) untuk mapping date→x dan line rows.",
        "Gunakan requestAnimationFrame untuk drag preview (jika drag diaktifkan).",
        "Virtualization ringan (opsional): hanya render rows yang terlihat (windowing) bila > 60 lines."
      ],
      "css": [
        "Gunakan will-change: transform hanya pada bar saat hover/drag.",
        "Gunakan contain: layout paint pada row container untuk isolasi repaint."
      ]
    },
    "tailwind_snippets": {
      "aps_root": "relative noise-overlay",
      "panel": "bg-[var(--card-surface)] border border-[var(--glass-border)] backdrop-blur-[var(--glass-blur)]",
      "sticky_header": "sticky top-0 z-20 bg-[var(--card-surface)]/80 backdrop-blur border-b border-[var(--glass-border)]",
      "sticky_left": "sticky left-0 z-30 bg-[var(--card-surface)]/90 backdrop-blur border-r border-[var(--glass-border)]",
      "grid_line": "bg-[color:var(--aps-grid-line)]",
      "weekend_shade": "bg-foreground/5"
    }
  },

  "image_urls": {
    "note": "APS dashboard tidak butuh foto. Gunakan visual murni (grid, chips, icons).",
    "decorative": []
  },

  "references": {
    "inspiration_links": [
      {
        "title": "Dribbble — glassmorphism dashboard tag",
        "url": "https://dribbble.com/tags/glassmorphism"
      },
      {
        "title": "Dribbble — gantt tag",
        "url": "https://dribbble.com/tags/gantt"
      },
      {
        "title": "Orizon — glassmorphism in 2026 (UX cautions)",
        "url": "https://www.orizon.co/blog/glassmorphism-in-2026-how-to-use-frosted-glass-without-killing-ux"
      }
    ]
  },

  "general_ui_ux_design_guidelines_appendix": "<General UI UX Design Guidelines>  \n    - You must **not** apply universal transition. Eg: `transition: all`. This results in breaking transforms. Always add transitions for specific interactive elements like button, input excluding transforms\n    - You must **not** center align the app container, ie do not add `.App { text-align: center; }` in the css file. This disrupts the human natural reading flow of text\n   - NEVER: use AI assistant Emoji characters like`🤖🧠💭💡🔮🎯📚🎭🎬🎪🎉🎊🎁🎀🎂🍰🎈🎨🎰💰💵💳🏦💎🪙💸🤑📊📈📉💹🔢🏆🥇 etc for icons. Always use **FontAwesome cdn** or **lucid-react** library already installed in the package.json\n\n **GRADIENT RESTRICTION RULE**\nNEVER use dark/saturated gradient combos (e.g., purple/pink) on any UI element.  Prohibited gradients: blue-500 to purple 600, purple 500 to pink-500, green-500 to blue-500, red to pink etc\nNEVER use dark gradients for logo, testimonial, footer etc\nNEVER let gradients cover more than 20% of the viewport.\nNEVER apply gradients to text-heavy content or reading areas.\nNEVER use gradients on small UI elements (<100px width).\nNEVER stack multiple gradient layers in the same viewport.\n\n**ENFORCEMENT RULE:**\n    • Id gradient area exceeds 20% of viewport OR affects readability, **THEN** use solid colors\n\n**How and where to use:**\n   • Section backgrounds (not content backgrounds)\n   • Hero section header content. Eg: dark to light to dark color\n   • Decorative overlays and accent elements only\n   • Hero section with 2-3 mild color\n   • Gradients creation can be done for any angle say horizontal, vertical or diagonal\n\n- For AI chat, voice application, **do not use purple color. Use color like light green, ocean blue, peach orange etc**\n\n</Font Guidelines>\n\n- Every interaction needs micro-animations - hover states, transitions, parallax effects, and entrance animations. Static = dead. \n   \n- Use 2-3x more spacing than feels comfortable. Cramped designs look cheap.\n\n- Subtle grain textures, noise overlays, custom cursors, selection states, and loading animations: separates good from extraordinary.\n   \n- Before generating UI, infer the visual style from the problem statement (palette, contrast, mood, motion) and immediately instantiate it by setting global design tokens (primary, secondary/accent, background, foreground, ring, state colors), rather than relying on any library defaults. Don't make the background dark as a default step, always understand problem first and define colors accordingly\n    Eg: - if it implies playful/energetic, choose a colorful scheme\n           - if it implies monochrome/minimal, choose a black–white/neutral scheme\n\n**Component Reuse:**\n\t- Prioritize using pre-existing components from src/components/ui when applicable\n\t- Create new components that match the style and conventions of existing components when needed\n\t- Examine existing components to understand the project's component patterns before creating new ones\n\n**IMPORTANT**: Do not use HTML based component like dropdown, calendar, toast etc. You **MUST** always use `/app/frontend/src/components/ui/ ` only as a primary components as these are modern and stylish component\n\n**Best Practices:**\n\t- Use Shadcn/UI as the primary component library for consistency and accessibility\n\t- Import path: ./components/[component-name]\n\n**Export Conventions:**\n\t- Components MUST use named exports (export const ComponentName = ...)\n\t- Pages MUST use default exports (export default function PageName() {...})\n\n**Toasts:**\n  - Use `sonner` for toasts\"\n  - Sonner component are located in `/app/src/components/ui/sonner.tsx`\n\nUse 2–4 color gradients, subtle textures/noise overlays, or CSS-based noise to avoid flat visuals.\n</General UI UX Design Guidelines>"
}
