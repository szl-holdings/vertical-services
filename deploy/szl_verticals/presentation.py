# SPDX-License-Identifier: Apache-2.0
"""Presentation-only native assets for the existing three public HTML owners.

Token payload and Orbit icon are embedded byte-exact subsets of accepted
szl-brand sources; see docs/NATIVE_PRESENTATION.json for immutable provenance.
No authority, source observations, network calls, or runtime bindings live here.
"""

NATIVE_TOKENS_CSS = r"""/* KANCHAY tokens v1.3.0 (derived): only the custom properties of
   szl-design-system.css. Palette, both polarities (on :root and on any
   [data-surface] element), type, spacing, radius, shadow, motion and z tokens.
   No element or class rules. Built by `szl-brand kanchay-build`; never edit by
   hand. Use it when a surface keeps its own component CSS.
   Brand assets (c) 2026 SZL Holdings, CC BY 4.0; code Apache-2.0. */
:root {
  --font-body:
    system-ui, -apple-system, "Segoe UI", "Helvetica Neue", "Liberation Sans",
    Arial, sans-serif;
  --font-display:
    system-ui, -apple-system, "Segoe UI", "Helvetica Neue", "Liberation Sans",
    Arial, sans-serif;
  --font-heading: var(--font-display);
  --font-mono:
    ui-monospace, "SF Mono", "Cascadia Code", "JetBrains Mono", "IBM Plex Mono",
    "Liberation Mono", Menlo, Consolas, monospace;
}
:root {
  /* yawar (blood / circulatory receipt ledger) — KEEP */
  --color-yawar-50:#fdecec; --color-yawar-100:#f9cfcf; --color-yawar-200:#f0a3a3;
  --color-yawar-300:#e57373; --color-yawar-400:#d65151; --color-yawar-500:#c0392b;
  --color-yawar-600:#a32a1f; --color-yawar-700:#822018; --color-yawar-800:#5e1712;
  --color-yawar-900:#3d0f0c;
  /* yuyay (thought / 13-axis heart gate) — KEEP; focus ring lives here */
  --color-yuyay-50:#e6f7f6; --color-yuyay-100:#bfeae8; --color-yuyay-200:#8fd9d5;
  --color-yuyay-300:#5cc4bf; --color-yuyay-400:#34aaa4; --color-yuyay-500:#168f89;
  --color-yuyay-600:#0f726e; --color-yuyay-700:#0b5957; --color-yuyay-800:#083f3e;
  --color-yuyay-900:#052827;
  /* hatun (great / premium accent, doctrine governance) — KEEP */
  --color-hatun-50:#faf5e9; --color-hatun-100:#f0e3c4; --color-hatun-200:#e4cf99;
  --color-hatun-300:#d7b96b; --color-hatun-400:#cda64a; --color-hatun-500:#c08f2f;
  --color-hatun-600:#a3741f; --color-hatun-700:#825a18; --color-hatun-800:#5e4012;
  --color-hatun-900:#3d290b;
  /* neutral gray scale — KEEP */
  --color-gray-50:#f5f7fa; --color-gray-100:#e6eaf1; --color-gray-200:#c9d2df;
  --color-gray-300:#a4b1c4; --color-gray-400:#76859b; --color-gray-500:#525f73;
  --color-gray-600:#3c4757; --color-gray-700:#2a3340; --color-gray-800:#1b222c;
  --color-gray-900:#10151c; --color-gray-950:#0a0f1e;
  /* NEW · canonical logo palette (founder-approved) */
  --color-space-900:#030F29; --color-space-800:#061536;
  --color-space-700:#0a1e47; --color-space-600:#102a5e;
  --color-coral-300:#F0917E; --color-coral-400:#DF735F; --color-coral-500:#C4543F;
  --color-silver-100:#E9EEF6; --color-silver-300:#9AA7BD; --color-silver-500:#5C6B86;
  /* NEW 1.3.0 · graphite operational neutrals and warm editorial neutrals (2026-10-06) */
  --color-graphite-950:#05070C; --color-graphite-900:#080B12; --color-graphite-800:#111722;
  --color-graphite-750:#141B27; --color-graphite-700:#182232; --color-graphite-600:#2B3749;
  --color-graphite-400:#71829B; --color-graphite-300:#8B98AC; --color-graphite-200:#AAB7C9;
  --color-graphite-50:#F1F4F8;
  --color-paper-100:#F5F3EE; --color-paper-200:#ECE9E2; --color-mist-100:#EBEEF2;
  --color-mist-200:#D6DBE3; --color-ink-600:#516075; --color-ink-500:#5E6A7C;
  --color-ink-400:#6E7A8C;
  --color-white:#FFFFFF; --color-ink:#0a0f1e; --color-ink-soft:#2a3340;
  /* semantic (status) — KEEP */
  --color-success:#1f9d57; --color-success-strong:#116b3d; --color-success-light:#3fce82;
  --color-warning:#c08f2f; --color-warning-light:#e4cf99;
  --color-error:#c0392b;   --color-error-light:#f0a3a3;
  --color-info:#2f7fb5;    --color-info-light:#7cb8e0;
}
:root, [data-surface="dark"] {
  --bg:var(--color-graphite-900); --bg-deep:var(--color-graphite-950);
  --surface:var(--color-graphite-800); --surface-alt:var(--color-graphite-750);
  --surface-raised:var(--color-graphite-700);
  --border:var(--color-graphite-600);
  --border-subtle:color-mix(in srgb, var(--color-graphite-600) 55%, transparent);
  --hairline:color-mix(in srgb, var(--color-silver-500) 38%, transparent);
  --control-edge:var(--color-graphite-400);
  --text:var(--color-graphite-50); --text-sub:var(--color-graphite-200);
  --text-ghost:var(--color-graphite-300);
  --accent:var(--color-coral-400); --accent-hover:var(--color-coral-300);
  --accent-press:var(--color-coral-500); --accent-ink:var(--color-space-900);
  /* Action fills are distinct from decorative coral: every small-text state must
     meet 4.5:1. Press keeps the legible fill and adds the button's tactile offset. */
  --action-bg:var(--color-coral-400); --action-hover-bg:var(--color-coral-300);
  --action-press-bg:var(--color-coral-400); --action-ink:var(--color-space-900);
  --hero-atmosphere:color-mix(in srgb, var(--color-space-700) 60%, transparent);
  --holo-silver:var(--color-silver-100); --holo-teal:var(--color-yuyay-300);
  --shadow-card:var(--shadow-sm); --shadow-card-hover:var(--shadow-md);
  --premium:var(--color-hatun-300);
  --link:var(--color-yuyay-200); --link-hover:var(--color-yuyay-100);
  --focus:var(--color-yuyay-400);
  --chip-ok:var(--color-success-light); --chip-warn:var(--color-warning-light);
  --chip-bad:var(--color-error-light);
  color-scheme:dark;
}
[data-surface="light"] {
  --bg:var(--color-paper-100); --bg-deep:var(--color-paper-200);
  --surface:var(--color-white); --surface-alt:var(--color-mist-100); --surface-raised:var(--color-white);
  --border:var(--color-mist-200);
  --border-subtle:color-mix(in srgb, var(--color-mist-200) 60%, transparent);
  --hairline:color-mix(in srgb, var(--color-silver-500) 30%, transparent);
  --control-edge:var(--color-ink-400);
  --text:var(--color-graphite-800); --text-sub:var(--color-ink-600);
  --text-ghost:var(--color-ink-500);
  --accent:var(--color-coral-500); --accent-hover:var(--color-coral-400);
  --accent-press:#a8442f; --accent-ink:var(--color-white);
  /* White on unmodified coral-500 is 4.48:1. This local navy mix preserves the
     palette primitive while making the small primary label legible. */
  --action-bg:color-mix(in srgb, var(--color-coral-500) 94%, var(--color-space-900));
  --action-hover-bg:var(--accent-press);
  --action-press-bg:color-mix(in srgb, var(--accent-press) 90%, var(--color-space-900));
  --action-ink:var(--color-white);
  --hero-atmosphere:color-mix(in srgb, var(--color-silver-300) 16%, transparent);
  --holo-silver:var(--color-silver-500); --holo-teal:var(--color-yuyay-700);
  --shadow-card:0 1px 2px rgba(3,15,41,.08);
  --shadow-card-hover:0 4px 16px rgba(3,15,41,.10);
  --premium:var(--color-hatun-700);
  --link:var(--color-yuyay-700); --link-hover:var(--color-yuyay-800);
  --focus:var(--color-yuyay-600);
  --chip-ok:var(--color-success-strong); --chip-warn:#6b4f00; --chip-bad:#9f281e;
  color-scheme:light;
}
:root, [data-surface="dark"], [data-surface="light"] {
  --shadow-focus:0 0 0 3px color-mix(in srgb, var(--focus) 55%, transparent);
  --holo-edge:linear-gradient(128deg, var(--holo-silver), var(--border) 24%,
    var(--holo-teal) 48%, var(--border) 72%, var(--holo-silver));
}
:root {
  --code-bg:var(--color-graphite-950); --code-ink:var(--color-graphite-50);
  --code-muted:var(--color-graphite-300); --code-border:var(--color-graphite-600);
  --code-edge:var(--color-graphite-400); --code-focus:var(--color-yuyay-400);
  --code-link:var(--color-yuyay-200); --code-link-hover:var(--color-yuyay-100);
  --code-string:var(--color-success-light); --code-number:var(--color-hatun-300);
}
:root {
  --text-xs:0.75rem; --text-sm:0.875rem; --text-base:1rem; --text-lg:1.25rem;
  --text-xl:1.563rem; --text-2xl:1.953rem; --text-3xl:2.441rem;
  --text-4xl:3.052rem; --text-5xl:3.815rem; --text-6xl:4.768rem;
  --leading-tight:1.1; --leading-snug:1.2; --leading-normal:1.6; --leading-mono:1.5;
  --tracking-tight:-0.011em; --tracking-normal:0; --tracking-caps:0.08em;
  --weight-regular:400; --weight-medium:500; --weight-semibold:600; --weight-bold:700;
}
:root {
  --space-px:1px; --space-1:.25rem; --space-2:.5rem; --space-3:.75rem; --space-4:1rem;
  --space-5:1.25rem; --space-6:1.5rem; --space-8:2rem; --space-10:2.5rem; --space-12:3rem;
  --space-16:4rem; --space-20:5rem; --space-24:6rem;
  --radius-sm:4px; --radius-md:8px; --radius-lg:12px; --radius-xl:16px;
  --radius-2xl:24px; --radius-full:9999px;
  --shadow-sm:0 1px 2px rgba(0,0,0,.40); --shadow-md:0 2px 8px rgba(0,0,0,.45);
  --shadow-lg:0 8px 24px rgba(0,0,0,.50); --shadow-xl:0 16px 48px rgba(0,0,0,.55);
  --shadow-glow-hatun:0 0 0 1px var(--color-hatun-500),
                      0 0 16px color-mix(in srgb, var(--color-hatun-400) 30%, transparent);
  --shadow-node:0 0 0 1px var(--color-coral-500),
                0 0 18px color-mix(in srgb, var(--color-coral-400) 32%, transparent);
  --ease-standard:cubic-bezier(.2,0,0,1); --ease-emphasized:cubic-bezier(.3,0,.1,1);
  --ease-out:cubic-bezier(0,0,.2,1); --ease-in:cubic-bezier(.4,0,1,1);
  --ease-orbit:cubic-bezier(.45,.05,.25,1);
  --duration-instant:75ms; --duration-fast:150ms; --duration-base:250ms;
  --duration-slow:400ms; --duration-slower:600ms; --duration-orbit:24s;
  --z-base:0; --z-raised:10; --z-dropdown:1000; --z-sticky:1100; --z-overlay:1200;
  --z-modal:1300; --z-popover:1400; --z-toast:1500; --z-max:2147483000;
  --z-control-dock:var(--z-popover);
  --border-hairline:1px; --border-thick:2px; --border-focus:3px;
  --measure:68ch; --container:1200px;
  --safe-area-top:env(safe-area-inset-top,0px);
  --safe-area-right:env(safe-area-inset-right,0px);
  --safe-area-bottom:env(safe-area-inset-bottom,0px);
  --safe-area-left:env(safe-area-inset-left,0px);
  --target-size-min:24px; --target-size-coarse:44px;
  --control-dock-max-inline-size:24rem;
}
"""

NATIVE_ICON_HTML = '<span class="native-mark"><img src="data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA2MDAgNjAwIiByb2xlPSJpbWciIGFyaWEtbGFiZWxsZWRieT0ic3psLWljb24tMzItdGl0bGUgc3psLWljb24tMzItZGVzYyI+PHRpdGxlIGlkPSJzemwtaWNvbi0zMi10aXRsZSI+U1pMIEhvbGRpbmdzPC90aXRsZT48ZGVzYyBpZD0ic3psLWljb24tMzItZGVzYyI+U1pMIGxldHRlcnMsIG9uZSBvcmJpdCBhbmQgdGhlIGNvcmFsIG5vZGUsIGZvciBwbGFjZW1lbnRzIG9mIDI0IHRvIDQ4IHBpeGVscy48L2Rlc2M+PHJlY3Qgd2lkdGg9IjYwMCIgaGVpZ2h0PSI2MDAiIHJ4PSIxMjAiIGZpbGw9IiMwMzBGMjkiLz48ZWxsaXBzZSBjeD0iMzAwIiBjeT0iMzAwIiByeD0iMjYyIiByeT0iMTIyIiBmaWxsPSJub25lIiBzdHJva2U9IiM5QUE3QkQiIHN0cm9rZS13aWR0aD0iMjIiIHRyYW5zZm9ybT0icm90YXRlKC0yMiAzMDAgMzAwKSIvPjxnIHRyYW5zZm9ybT0idHJhbnNsYXRlKDMwMCAzMDApIHNjYWxlKDEuMikgdHJhbnNsYXRlKC0yOTkuOCAtMjk5LjEpIj48ZyBmaWxsPSIjMDMwRjI5IiBzdHJva2U9IiMwMzBGMjkiIHN0cm9rZS13aWR0aD0iMTguMzMiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxwYXRoIGQ9Ik0yMjguMjU2IDMzMS4wNDlRMjI4LjI1NiAzNTMuOTY3IDIxMS4yNiAzNjYuMDkxUTE5NC4yNjUgMzc4LjIxNCAxNjEuMzgzIDM3OC4yMTRRMTMxLjM3OCAzNzguMjE0IDExNC4zMjggMzY3LjU4NlE5Ny4yNzggMzU2Ljk1NyA5Mi40MDYgMzM1LjM2N0wxMjMuOTYgMzMwLjE2M1ExMjcuMTcxIDM0Mi41NjQgMTM2LjQ3MSAzNDguMTU1UTE0NS43NzEgMzUzLjc0NiAxNjIuMjY4IDM1My43NDZRMTk2LjQ4IDM1My43NDYgMTk2LjQ4IDMzMi45MzFRMTk2LjQ4IDMyNi4yODggMTkyLjU0OSAzMjEuOTdRMTg4LjYxOSAzMTcuNjUyIDE4MS40NzggMzE0Ljc3NFExNzQuMzM2IDMxMS44OTUgMTU0LjA3NSAzMDcuNzk4UTEzNi41ODIgMzAzLjcwMiAxMjkuNzE4IDMwMS4yMTFRMTIyLjg1MyAyOTguNzIgMTE3LjMxNyAyOTUuMzQzUTExMS43ODEgMjkxLjk2NiAxMDcuOTA2IDI4Ny4yMDVRMTA0LjAzMSAyODIuNDQ0IDEwMS44NzIgMjc2LjAyM1E5OS43MTMgMjY5LjYwMSA5OS43MTMgMjYxLjI5N1E5OS43MTMgMjQwLjE1IDExNS42MDEgMjI4LjkxM1ExMzEuNDg5IDIxNy42NzUgMTYxLjgyNSAyMTcuNjc1UTE5MC44MzMgMjE3LjY3NSAyMDUuMzkyIDIyNi43NTRRMjE5Ljk1MiAyMzUuODMzIDIyNC4xNTkgMjU2Ljc1OEwxOTIuNDk0IDI2MS4wNzZRMTkwLjA1OCAyNTEuMDAxIDE4Mi41ODUgMjQ1LjkwOFExNzUuMTExIDI0MC44MTUgMTYxLjE2MSAyNDAuODE1UTEzMS40ODkgMjQwLjgxNSAxMzEuNDg5IDI1OS40MTVRMTMxLjQ4OSAyNjUuNTA1IDEzNC42NDQgMjY5LjM4UTEzNy44IDI3My4yNTUgMTQ0IDI3NS45NjdRMTUwLjIgMjc4LjY4IDE2OS4xMzMgMjgyLjc3NlExOTEuNjA4IDI4Ny41MzcgMjAxLjI5NiAyOTEuNTc4UTIxMC45ODQgMjk1LjYyIDIxNi42MyAzMDAuOTg5UTIyMi4yNzcgMzA2LjM1OSAyMjUuMjY2IDMxMy44MzNRMjI4LjI1NiAzMjEuMzA2IDIyOC4yNTYgMzMxLjA0OVoiLz48cGF0aCBkPSJNMzY5LjA4NyAzNzZIMjQzLjg2N1YzNTIuODZMMzI4LjIzMyAyNDUuNTc2SDI1Mi4yODFWMjIwSDM2NC41NDhWMjQyLjY5N0wyODAuMTgyIDM1MC40MjRIMzY5LjA4N1oiLz48cGF0aCBkPSJNMzkwLjc4OCAzNzZWMjIwSDQyMy40NDlWMzUwLjc1N0g1MDcuMTUxVjM3NloiLz48L2c+PGcgZmlsbD0iI0ZGRkZGRiI+PHBhdGggZD0iTTIyOC4yNTYgMzMxLjA0OVEyMjguMjU2IDM1My45NjcgMjExLjI2IDM2Ni4wOTFRMTk0LjI2NSAzNzguMjE0IDE2MS4zODMgMzc4LjIxNFExMzEuMzc4IDM3OC4yMTQgMTE0LjMyOCAzNjcuNTg2UTk3LjI3OCAzNTYuOTU3IDkyLjQwNiAzMzUuMzY3TDEyMy45NiAzMzAuMTYzUTEyNy4xNzEgMzQyLjU2NCAxMzYuNDcxIDM0OC4xNTVRMTQ1Ljc3MSAzNTMuNzQ2IDE2Mi4yNjggMzUzLjc0NlExOTYuNDggMzUzLjc0NiAxOTYuNDggMzMyLjkzMVExOTYuNDggMzI2LjI4OCAxOTIuNTQ5IDMyMS45N1ExODguNjE5IDMxNy42NTIgMTgxLjQ3OCAzMTQuNzc0UTE3NC4zMzYgMzExLjg5NSAxNTQuMDc1IDMwNy43OThRMTM2LjU4MiAzMDMuNzAyIDEyOS43MTggMzAxLjIxMVExMjIuODUzIDI5OC43MiAxMTcuMzE3IDI5NS4zNDNRMTExLjc4MSAyOTEuOTY2IDEwNy45MDYgMjg3LjIwNVExMDQuMDMxIDI4Mi40NDQgMTAxLjg3MiAyNzYuMDIzUTk5LjcxMyAyNjkuNjAxIDk5LjcxMyAyNjEuMjk3UTk5LjcxMyAyNDAuMTUgMTE1LjYwMSAyMjguOTEzUTEzMS40ODkgMjE3LjY3NSAxNjEuODI1IDIxNy42NzVRMTkwLjgzMyAyMTcuNjc1IDIwNS4zOTIgMjI2Ljc1NFEyMTkuOTUyIDIzNS44MzMgMjI0LjE1OSAyNTYuNzU4TDE5Mi40OTQgMjYxLjA3NlExOTAuMDU4IDI1MS4wMDEgMTgyLjU4NSAyNDUuOTA4UTE3NS4xMTEgMjQwLjgxNSAxNjEuMTYxIDI0MC44MTVRMTMxLjQ4OSAyNDAuODE1IDEzMS40ODkgMjU5LjQxNVExMzEuNDg5IDI2NS41MDUgMTM0LjY0NCAyNjkuMzhRMTM3LjggMjczLjI1NSAxNDQgMjc1Ljk2N1ExNTAuMiAyNzguNjggMTY5LjEzMyAyODIuNzc2UTE5MS42MDggMjg3LjUzNyAyMDEuMjk2IDI5MS41NzhRMjEwLjk4NCAyOTUuNjIgMjE2LjYzIDMwMC45ODlRMjIyLjI3NyAzMDYuMzU5IDIyNS4yNjYgMzEzLjgzM1EyMjguMjU2IDMyMS4zMDYgMjI4LjI1NiAzMzEuMDQ5WiIvPjxwYXRoIGQ9Ik0zNjkuMDg3IDM3NkgyNDMuODY3VjM1Mi44NkwzMjguMjMzIDI0NS41NzZIMjUyLjI4MVYyMjBIMzY0LjU0OFYyNDIuNjk3TDI4MC4xODIgMzUwLjQyNEgzNjkuMDg3WiIvPjxwYXRoIGQ9Ik0zOTAuNzg4IDM3NlYyMjBINDIzLjQ0OVYzNTAuNzU3SDUwNy4xNTFWMzc2WiIvPjwvZz48L2c+PGNpcmNsZSBjeD0iMzczLjY5IiBjeT0iMTU0LjA1IiByPSIzMCIgZmlsbD0iI0RGNzM1RiIvPjwvc3ZnPgo=" width="32" height="32" alt="" /></span>'

NATIVE_INTERFACE_CSS = r"""/* Native public presentation. Per-vertical motifs and runtime evidence stay owned by their source. */
:root { --ink: var(--text); --muted: var(--text-sub); --faint: var(--text-sub); }
body { font-family: var(--font-body); font-size: 16px; line-height: 1.6; }
:where(a,button,input,textarea,select,summary,[tabindex]):focus-visible { outline: 3px solid var(--focus); outline-offset: 4px; }
:where(a,button,input,textarea,select) { min-height: 44px; }
.native-mark { display: inline-flex; flex: 0 0 48px; padding: 8px; }
.native-mark img { display: block; width: 32px; height: 32px; max-width: none; }
.brand { display: inline-flex; align-items: center; gap: .4rem; max-width: 100%; }
.brand,.eyebrow,.datum-id,.mono,.micro { font-size: .75rem; line-height: 1.55; letter-spacing: .09em; }
.top { padding-bottom: 1.25rem; border-bottom: 1px solid var(--line); }
.navigation a,.nav a { font-size: .875rem; text-underline-offset: .22em; }
.navigation a { min-width: 44px; justify-content: center; text-decoration: none; color: var(--text-sub); }
.navigation a:hover { color: var(--text); text-decoration: underline; }
.nav a { border-color: var(--control-edge); border-radius: .6rem; }
.rail { position: relative; }
.rail::after { content: ""; position: absolute; inset: auto 0 -1px; height: 1px; background: var(--holo-edge); pointer-events: none; }
.identity { gap: .4rem; }
.identity strong { font-size: .875rem; }
.family { flex-wrap: wrap; overflow: visible; gap: .25rem; }
.family a { font-size: .75rem; line-height: 1.5; letter-spacing: .045em; padding: .5rem .75rem; }
.family a[aria-current="page"] { border-color: var(--control-edge); }
h1 { font-weight: 550; }
h2,h3 { line-height: 1.12; }
.lede { line-height: 1.6; }
.pill { font-size: .8125rem; line-height: 1.55; border-radius: .6rem; }
.instrument { border-radius: 1.2rem; box-shadow: 0 1.5rem 4rem rgb(0 0 0 / .2); }
.instrument li { gap: 1rem; }
.instrument li strong { font-size: .8125rem; line-height: 1.5; }
.instrument-copy { border-radius: .8rem; }
.reading small,.stat small { color: var(--text-sub); font-size: .75rem; line-height: 1.55; letter-spacing: .055em; }
.reading strong { font-size: .875rem; line-height: 1.5; }
.state { font-size: .75rem; line-height: 1.4; letter-spacing: .025em; }
.asset-top { flex-wrap: wrap; }
.asset-foot,.idea small,footer { font-size: .75rem; line-height: 1.6; color: var(--text-sub); }
.datum small,.card small { font-size: .875rem; }
.button { font: 650 .875rem/1.5 var(--font-body); letter-spacing: 0; text-transform: none; border-color: var(--control-edge); border-radius: .6rem; }
.button.primary,.actions a.primary-action { background: var(--action-bg); color: var(--action-ink); border: 1px solid var(--action-bg); font-weight: 700; }
.button.primary:hover,.actions a.primary-action:hover { background: var(--action-hover-bg); border-color: var(--action-hover-bg); }
.boundary { font-size: .9375rem; line-height: 1.7; }
.boundary strong { color: var(--text); }
pre { background: var(--code-bg); color: var(--code-ink); border-color: var(--code-border); font: .875rem/1.65 var(--font-mono); }
[data-native-view="index"] { --bg: var(--color-graphite-900); --panel: var(--surface); --line: var(--border); }
[data-native-view="index"] body { background: radial-gradient(ellipse at 80% 0,var(--hero-atmosphere),transparent 65%),var(--bg); }
[data-native-view="index"] .shell { width: min(1240px,100%); }
[data-native-view="index"] h1 { margin-top: 3rem; font-size: clamp(2.5rem,7.5cqi,5.25rem); line-height: 1.02; }
[data-native-view="index"] .brand,[data-native-view="index"] .eyebrow { color: var(--text-sub); }
[data-native-view="index"] .card { min-height: 21rem; padding: 1.5rem; background: var(--surface); border-radius: 1rem; }
[data-native-view="index"] .card h2 { font-size: 1.75rem; letter-spacing: -.035em; }
[data-native-view="index"] .card p { font-size: .9375rem; }
[data-native-view="index"] .actions { gap: .5rem; }
[data-native-view="index"] .actions a { font-size: .875rem; line-height: 1.5; padding: .5rem .65rem; border: 1px solid var(--control-edge); border-radius: .5rem; }
[data-native-view="index"] .actions a.primary-action { border-color: var(--action-bg); }
[data-native-view="intelligence"] .hero { min-height: 0; padding-block: clamp(3rem,6cqi,5.5rem); }
[data-native-view="intelligence"] section { padding-block: clamp(2.75rem,5.5cqi,5.5rem); }
[data-native-view="intelligence"] .section-head h2 { line-height: 1.06; }
[data-native-view="intelligence"] .thesis h3 { line-height: 1.1; }
[data-native-view="workspace"] .hero { align-items: start; padding-block: clamp(3rem,6cqi,5rem); }
[data-native-view="workspace"] h1 { font-size: clamp(2.5rem,8cqi,5.5rem); line-height: 1.04; }
[data-native-view="workspace"] .instrument { min-height: 0; }
[data-native-view="workspace"] .instrument > strong { font-size: clamp(1.5rem,3cqi,2rem); line-height: 1.2; margin-block: .8rem; }
[data-native-view="workspace"] .instrument li { display: grid; grid-template-columns: minmax(5rem,.4fr) minmax(0,1fr); }
[data-native-view="workspace"] .instrument li > span { overflow-wrap: normal; }
@media (prefers-contrast:more) { :root { --line: var(--control-edge); } }
@media (pointer:coarse) { a,button,input,textarea,select { min-height: 48px; } }
@media (prefers-reduced-motion:reduce) { *,*::before,*::after { animation:none!important; transition:none!important; scroll-behavior:auto!important; } }
@media (forced-colors:active) { .rail::after,.field,.instrument::before { display:none; } .button.primary,.actions a.primary-action { border: 2px solid ButtonText; } }
@media print { .field,.instrument::before { display:none; } .rail { position:static; } }
"""
