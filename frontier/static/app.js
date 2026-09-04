/* SPDX-License-Identifier: Apache-2.0 */
(() => {
  "use strict";

  const appRoot = document.querySelector("[data-app]");
  const boot = document.querySelector("[data-boot]");
  const menuButton = document.querySelector("[data-menu]");
  const mobileNav = document.querySelector("[data-mobile-nav]");
  const navAllButton = document.querySelector("[data-nav-all]");
  const navDrawer = document.querySelector("[data-nav-drawer]");
  const navGrid = document.querySelector("[data-nav-grid]");
  const mobileGrid = document.querySelector("[data-mobile-grid]");
  const toast = document.querySelector("[data-toast]");

  const state = {
    registry: null,
    search: "",
    category: "all",
    currentReceipt: null,
    currentSnapshot: null,
  };

  const instrumentBuilders = {
    a11oy: renderDecisionRibbon,
    killinchu: renderTheaterMap,
    lyte: renderSignalWaterfall,
    sentra: renderExposureGraph,
    terra: renderParcelStack,
    puriq: renderResearchTerminal,
    prism: renderCitationRail,
    anatomy: renderOrganBody,
  };

  function node(tag, attributes = {}, children = []) {
    const element = document.createElement(tag);
    for (const [key, value] of Object.entries(attributes)) {
      if (value === null || value === undefined || value === false) continue;
      if (key === "class") {
        element.className = value;
      } else if (key === "text") {
        element.textContent = String(value);
      } else if (key === "html") {
        element.innerHTML = String(value);
      } else if (key === "dataset") {
        for (const [dataKey, dataValue] of Object.entries(value)) {
          element.dataset[dataKey] = String(dataValue);
        }
      } else if (key === "style") {
        for (const [property, styleValue] of Object.entries(value)) {
          element.style.setProperty(property, String(styleValue));
        }
      } else if (key === "checked") {
        element.checked = Boolean(value);
      } else if (key === "value") {
        element.value = String(value);
      } else if (key === "disabled") {
        element.disabled = Boolean(value);
      } else {
        element.setAttribute(key, String(value));
      }
    }
    const list = Array.isArray(children) ? children : [children];
    for (const child of list) {
      if (child === null || child === undefined || child === false) continue;
      element.append(child instanceof Node ? child : document.createTextNode(String(child)));
    }
    return element;
  }

  function textLink(label, href, { route = false, external = false, className = "text-link" } = {}) {
    const link = node("a", { class: className, href });
    if (route) link.dataset.route = "";
    if (external) {
      link.target = "_blank";
      link.rel = "noreferrer";
    }
    link.append(node("span", { text: label }), node("span", { class: "arrow", "aria-hidden": "true", text: "→" }));
    return link;
  }

  function button(label, className = "button", type = "button") {
    return node("button", { class: className, type, text: label });
  }

  function chip(label, stateValue = null) {
    const attributes = { class: stateValue ? "status-chip" : "chip", text: label };
    if (stateValue) attributes.dataset = { state: stateValue };
    return node("span", attributes);
  }

  function showToast(message) {
    if (!toast) return;
    toast.textContent = message;
    toast.hidden = false;
    window.clearTimeout(showToast.timer);
    showToast.timer = window.setTimeout(() => {
      toast.hidden = true;
    }, 3600);
  }

  function closeMenus() {
    if (menuButton && mobileNav) {
      menuButton.setAttribute("aria-expanded", "false");
      menuButton.querySelector(".sr-only").textContent = "Open navigation";
      mobileNav.hidden = true;
    }
    if (navAllButton && navDrawer) {
      navAllButton.setAttribute("aria-expanded", "false");
      navDrawer.hidden = true;
    }
    document.body.classList.remove("nav-open");
  }

  function toggleMobileMenu() {
    if (!menuButton || !mobileNav) return;
    const next = menuButton.getAttribute("aria-expanded") !== "true";
    closeMenus();
    menuButton.setAttribute("aria-expanded", String(next));
    menuButton.querySelector(".sr-only").textContent = next ? "Close navigation" : "Open navigation";
    mobileNav.hidden = !next;
    document.body.classList.toggle("nav-open", next);
  }

  function toggleNavDrawer() {
    if (!navAllButton || !navDrawer) return;
    const next = navAllButton.getAttribute("aria-expanded") !== "true";
    closeMenus();
    navAllButton.setAttribute("aria-expanded", String(next));
    navDrawer.hidden = !next;
  }

  function navigate(href, { replace = false, focus = true } = {}) {
    const target = new URL(href, window.location.origin);
    if (target.origin !== window.location.origin) {
      window.location.assign(target.href);
      return;
    }
    if (replace) {
      window.history.replaceState({}, "", target.pathname + target.search + target.hash);
    } else {
      window.history.pushState({}, "", target.pathname + target.search + target.hash);
    }
    closeMenus();
    renderRoute();
    if (focus) {
      document.querySelector("#content")?.focus({ preventScroll: true });
      window.scrollTo({ top: 0, behavior: prefersReducedMotion() ? "auto" : "smooth" });
    }
  }

  function prefersReducedMotion() {
    return window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  function setMetadata(title, description) {
    document.title = title;
    const descriptionMeta = document.querySelector('meta[name="description"]');
    const ogTitle = document.querySelector('meta[property="og:title"]');
    const ogDescription = document.querySelector('meta[property="og:description"]');
    if (descriptionMeta) descriptionMeta.setAttribute("content", description);
    if (ogTitle) ogTitle.setAttribute("content", title);
    if (ogDescription) ogDescription.setAttribute("content", description);
  }

  async function fetchJson(url, options = {}) {
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), options.timeout || 12000);
    try {
      const response = await fetch(url, {
        method: options.method || "GET",
        headers: options.body ? { "Content-Type": "application/json" } : undefined,
        body: options.body ? JSON.stringify(options.body) : undefined,
        signal: controller.signal,
        credentials: "same-origin",
      });
      let payload;
      try {
        payload = await response.json();
      } catch {
        payload = { error: "INVALID_JSON", message: `HTTP ${response.status}` };
      }
      if (!response.ok) {
        const error = new Error(payload.message || payload.error || `HTTP ${response.status}`);
        error.payload = payload;
        error.status = response.status;
        throw error;
      }
      return payload;
    } finally {
      window.clearTimeout(timer);
    }
  }

  function registerGlobalEvents() {
    document.addEventListener("click", (event) => {
      const routeLink = event.target.closest("a[data-route]");
      if (routeLink && routeLink.origin === window.location.origin && !event.metaKey && !event.ctrlKey && !event.shiftKey && event.button === 0) {
        event.preventDefault();
        navigate(routeLink.pathname + routeLink.search + routeLink.hash);
      }
      if (navDrawer && !navDrawer.hidden && !event.target.closest("[data-nav-drawer]") && !event.target.closest("[data-nav-all]")) {
        closeMenus();
      }
    });

    window.addEventListener("popstate", () => {
      closeMenus();
      renderRoute();
    });

    window.addEventListener("keydown", (event) => {
      if (event.key === "Escape") closeMenus();
    });

    menuButton?.addEventListener("click", toggleMobileMenu);
    navAllButton?.addEventListener("click", toggleNavDrawer);
  }

  function renderNavigation() {
    const registry = state.registry;
    if (!registry) return;
    navGrid.replaceChildren();
    mobileGrid.replaceChildren();

    for (const vertical of registry.verticals) {
      const accent = vertical.experience.palette[2];
      const makeItem = (className) => {
        const link = node("a", {
          class: className,
          href: `/v/${vertical.slug}`,
          dataset: { route: "" },
          style: { "--system-accent": accent },
        });
        link.append(
          node("span", { class: "nav-system-signal", "aria-hidden": "true" }),
          node("span", { class: "nav-system-copy" }, [
            node("strong", { text: vertical.name }),
            node("small", { text: vertical.category }),
          ]),
        );
        return link;
      };
      navGrid.append(makeItem("nav-system"));
      mobileGrid.append(makeItem("mobile-system"));
    }
  }

  function updateHeaderCurrent(slug = null) {
    document.querySelectorAll(".desktop-nav a[data-route]").forEach((link) => {
      const active = slug ? link.pathname === `/v/${slug}` : link.pathname === "/";
      if (active) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    });
  }

  function currentSlug() {
    const match = window.location.pathname.match(/^\/v\/([a-z0-9-]+)\/?$/);
    return match ? match[1] : null;
  }

  function renderRoute() {
    if (!state.registry) return;
    state.currentReceipt = null;
    state.currentSnapshot = null;
    const slug = currentSlug();
    if (slug) {
      const vertical = state.registry.verticals.find((row) => row.slug === slug);
      if (!vertical) {
        renderNotFound(slug);
        return;
      }
      updateHeaderCurrent(slug);
      renderVertical(vertical);
      return;
    }
    if (window.location.pathname !== "/" && window.location.pathname !== "/index.html") {
      renderNotFound(window.location.pathname);
      return;
    }
    updateHeaderCurrent(null);
    renderPortfolio();
  }

  function renderNotFound(value) {
    setMetadata("System not found · SZL Vertical Frontier", "The requested SZL vertical does not exist.");
    const shell = node("div", { class: "error-state" });
    const card = node("section", { class: "error-card" });
    card.append(
      node("p", { class: "eyebrow", text: "404 · Unbound route" }),
      node("h1", { text: "That system is not in the registry." }),
      node("p", { text: `No public vertical is bound to “${String(value).slice(0, 100)}”.` }),
      textLink("Return to the portfolio", "/", { route: true, className: "button button-primary" }),
    );
    shell.append(card);
    appRoot.replaceChildren(shell);
  }

  function uniqueBindingCount(kind) {
    const values = new Set();
    for (const vertical of state.registry.verticals) {
      for (const row of vertical[kind] || []) values.add(row.id);
    }
    return values.size;
  }

  function renderPortfolio() {
    setMetadata(
      "SZL Vertical Frontier · Eight governed command systems",
      "Eight original vertical experiences built on one evidence, kernel, model-routing, and human-approval fabric.",
    );
    const registry = state.registry;
    const shell = node("div", { class: "page-shell portfolio-page" });

    const hero = node("section", { class: "container portfolio-hero" });
    const copy = node("div", { class: "portfolio-hero-copy" });
    copy.append(
      node("p", { class: "kicker", text: "One governed fabric · Eight distinct systems" }),
      node("h1", { class: "portfolio-title", html: "Not one skin.<br><em>Eight original command languages.</em>" }),
      node("p", {
        class: "portfolio-lede",
        text: "Each vertical owns a different visual instrument, operating wedge, official-source boundary, model route, and proof path. The shared substrate keeps policy, evidence, memory, and human authority consistent without flattening the products into copies of one another.",
      }),
    );
    const actions = node("div", { class: "hero-actions" });
    actions.append(
      textLink("Explore the systems", "#systems", { className: "button button-primary" }),
      textLink("Open SZL Atlas", "https://huggingface.co/spaces/SZLHOLDINGS/szl-command-lab", { external: true, className: "button" }),
      textLink("Inspect evidence", "https://a11oy.net", { external: true }),
    );
    copy.append(actions);
    hero.append(copy);

    const proofbar = node("div", { class: "portfolio-proofbar", "aria-label": "Portfolio contract" });
    const proofData = [
      [registry.verticals.length, "distinct verticals"],
      [uniqueBindingCount("models"), "governed model routes"],
      [uniqueBindingCount("kernels"), "portable kernel families"],
      [registry.verticals.reduce((sum, row) => sum + row.sources.length, 0), "official-source contracts"],
    ];
    for (const [value, label] of proofData) {
      proofbar.append(node("div", { class: "proof-cell" }, [node("strong", { text: value }), node("span", { text: label })]));
    }
    hero.append(proofbar);
    shell.append(hero);

    const systems = node("section", { class: "container portfolio-section", id: "systems" });
    const heading = node("div", { class: "section-heading" });
    heading.append(
      node("div", {}, [
        node("p", { class: "section-kicker", text: "Portfolio map" }),
        node("h2", { class: "section-title", text: "Choose the operating problem, not a generic dashboard." }),
      ]),
      node("p", {
        class: "section-lede",
        text: "Every system is optimized for a different decision surface. Search by mission, evidence source, model, kernel, or category.",
      }),
    );
    systems.append(heading);

    const toolbar = node("div", { class: "portfolio-toolbar" });
    const searchWrap = node("label", { class: "search-field" });
    searchWrap.append(node("span", { class: "sr-only", text: "Search vertical systems" }));
    const search = node("input", {
      type: "search",
      placeholder: "Search systems, sources, models, kernels…",
      value: state.search,
      autocomplete: "off",
    });
    searchWrap.append(search);

    const categoryWrap = node("label", { class: "select-field" });
    categoryWrap.append(node("span", { class: "sr-only", text: "Filter by category" }));
    const select = node("select", { "aria-label": "Filter by category" });
    const categories = ["all", ...new Set(registry.verticals.map((row) => row.category))];
    for (const category of categories) {
      const option = node("option", { value: category, text: category === "all" ? "All categories" : category });
      if (category === state.category) option.selected = true;
      select.append(option);
    }
    categoryWrap.append(select);
    toolbar.append(searchWrap, categoryWrap);
    systems.append(toolbar);

    const grid = node("div", { class: "system-grid", "aria-live": "polite" });
    systems.append(grid);

    const paint = () => {
      const query = state.search.trim().toLowerCase();
      const visible = registry.verticals.filter((vertical) => {
        if (state.category !== "all" && vertical.category !== state.category) return false;
        const haystack = [
          vertical.name,
          vertical.category,
          vertical.promise,
          vertical.unserved_wedge,
          vertical.experience.layout,
          vertical.experience.instrument,
          ...vertical.models.map((row) => `${row.id} ${row.role}`),
          ...vertical.kernels.map((row) => `${row.id} ${row.role}`),
          ...vertical.sources.map((row) => `${row.id} ${row.host} ${row.purpose}`),
        ].join(" ").toLowerCase();
        return !query || haystack.includes(query);
      });
      grid.replaceChildren();
      if (!visible.length) {
        grid.append(node("div", { class: "no-results", text: "No vertical matches that source, model, kernel, or mission." }));
        return;
      }
      visible.forEach((vertical, index) => grid.append(renderSystemCard(vertical, registry.verticals.indexOf(vertical) + 1)));
    };

    search.addEventListener("input", () => {
      state.search = search.value;
      paint();
    });
    select.addEventListener("change", () => {
      state.category = select.value;
      paint();
    });
    paint();
    shell.append(systems);

    const edge = node("section", { class: "edge-band" });
    const edgeInner = node("div", { class: "container vertical-section" });
    const edgeHeading = node("div", { class: "section-heading" });
    edgeHeading.append(
      node("div", {}, [
        node("p", { class: "section-kicker", text: "The shared advantage" }),
        node("h2", { class: "section-title", text: "One evidence spine compounds across every market." }),
      ]),
      node("p", {
        class: "section-lede",
        text: "The products stay visually and operationally distinct, while the decision ontology, receipt chain, session memory, and human-binding rule improve together.",
      }),
    );
    edgeInner.append(edgeHeading);
    const edgeGrid = node("div", { class: "edge-grid" });
    registry.shared_edge.slice(0, 8).forEach((item, index) => {
      edgeGrid.append(node("article", { class: "edge-card" }, [
        node("span", { class: "edge-number", text: String(index + 1).padStart(2, "0") }),
        node("h3", { text: titleCase(item) }),
        node("p", { text: edgeExplanation(item) }),
      ]));
    });
    edgeInner.append(edgeGrid);
    edge.append(edgeInner);
    shell.append(edge);

    const boundary = node("section", { class: "container portfolio-section" });
    boundary.append(
      node("div", { class: "section-heading" }, [
        node("div", {}, [
          node("p", { class: "section-kicker", text: "Non-negotiable boundary" }),
          node("h2", { class: "section-title", text: "Original systems, lawful inputs, checkable claims." }),
        ]),
        node("p", {
          class: "section-lede",
          text: "We extract product patterns and adopt official data or compatible open-source primitives. We do not copy proprietary source code, private datasets, protected trade dress, or unsupported performance claims.",
        }),
      ]),
      node("div", { class: "action-row" }, [
        textLink("Enter A11oy", "https://a-11-oy.com", { external: true, className: "button button-primary" }),
        textLink("Audit the source", "https://github.com/szl-holdings/vertical-services", { external: true, className: "button" }),
      ]),
    );
    shell.append(boundary);

    appRoot.replaceChildren(shell);
  }

  function renderSystemCard(vertical, index) {
    const accent = vertical.experience.palette[2];
    const link = node("a", {
      class: "system-card",
      href: `/v/${vertical.slug}`,
      dataset: { route: "" },
      style: { "--card-accent": accent },
      "aria-label": `Open ${vertical.name}: ${vertical.promise}`,
    });
    link.append(
      node("div", { class: "system-card-top" }, [
        node("span", { class: "system-index", text: String(index).padStart(2, "0") }),
        node("span", { class: "system-layout", text: vertical.experience.instrument.replaceAll("-", " ") }),
      ]),
      node("h3", { class: "system-name", text: vertical.name }),
      node("p", { class: "system-category", text: vertical.category }),
      node("p", { class: "system-promise", text: vertical.promise }),
    );
    const bottom = node("div", { class: "system-card-bottom" });
    const bindings = node("div", { class: "system-bindings" });
    bindings.append(chip(`${vertical.models.length} models`), chip(`${vertical.kernels.length} kernels`), chip(`${vertical.sources.length} sources`));
    bottom.append(bindings, node("span", { class: "text-link" }, [node("span", { text: "Open" }), node("span", { class: "arrow", "aria-hidden": "true", text: "→" })]));
    link.append(bottom);
    return link;
  }

  function renderVertical(vertical) {
    setMetadata(`${vertical.name} · SZL Vertical Frontier`, `${vertical.promise} ${vertical.unserved_wedge}`);
    const palette = vertical.experience.palette;
    const shell = node("div", {
      class: `page-shell vertical-page theme-${vertical.slug}`,
      style: {
        "--page-bg": palette[0],
        "--theme-text": palette[1],
        "--accent": palette[2],
        "--accent-2": palette[3],
        "--surface": palette[4],
        "--surface-2": mixHex(palette[4], palette[0], 0.62),
      },
    });

    const hero = node("section", { class: "container vertical-hero" });
    const copy = node("div", { class: "vertical-copy" });
    const breadcrumbs = node("nav", { class: "breadcrumbs", "aria-label": "Breadcrumb" });
    breadcrumbs.append(
      node("a", { href: "/", text: "Portfolio", dataset: { route: "" } }),
      node("span", { "aria-hidden": "true", text: "/" }),
      node("span", { text: vertical.name, "aria-current": "page" }),
    );
    const meta = node("div", { class: "vertical-meta" });
    meta.append(chip(vertical.category), chip(vertical.experience.layout.replaceAll("-", " ")));
    copy.append(
      breadcrumbs,
      meta,
      node("h1", { class: "vertical-title", text: vertical.name }),
      node("p", { class: "vertical-hero-line", text: vertical.experience.hero }),
      node("p", { class: "vertical-promise", text: vertical.promise }),
    );
    const actions = node("div", { class: "vertical-actions" });
    const runButton = button("Run the evidence cycle", "button button-accent");
    runButton.addEventListener("click", () => document.querySelector("#workbench")?.scrollIntoView({ behavior: prefersReducedMotion() ? "auto" : "smooth" }));
    actions.append(
      runButton,
      textLink("Inspect bindings", "#bindings", { className: "button" }),
      textLink("Back to portfolio", "/", { route: true }),
    );
    copy.append(actions);
    hero.append(copy, createInstrument(vertical));
    shell.append(hero);

    const overview = node("section", { class: "container vertical-section" });
    const overviewGrid = node("div", { class: "vertical-overview" });
    const wedge = node("div", { class: "wedge-card" });
    wedge.append(
      node("p", { class: "section-kicker", text: "The open market wedge" }),
      node("blockquote", { text: vertical.unserved_wedge }),
      node("p", { text: "This is the lane: a concrete operating problem competitors often split across dashboards, copilots, data vendors, and manual approval chains." }),
    );
    const facts = node("dl", { class: "overview-facts" });
    const factRows = [
      ["Visual language", vertical.experience.layout.replaceAll("-", " ")],
      ["Primary instrument", vertical.experience.instrument.replaceAll("-", " ")],
      ["Interaction model", vertical.experience.interaction],
      ["Decision boundary", "Proposal only · human binding required"],
    ];
    for (const [term, description] of factRows) {
      facts.append(node("div", { class: "fact" }, [node("dt", { text: term }), node("dd", { text: description })]));
    }
    overviewGrid.append(wedge, facts);
    overview.append(overviewGrid);
    shell.append(overview);

    shell.append(renderBindingsSection(vertical));
    shell.append(renderSourcesSection(vertical));
    shell.append(renderWorkbench(vertical));
    shell.append(renderBoundary(vertical));
    appRoot.replaceChildren(shell);
  }

  function createInstrument(vertical) {
    const figure = node("figure", {
      class: "instrument-shell",
      role: "img",
      "aria-label": `${vertical.name} ${vertical.experience.instrument.replaceAll("-", " ")} — an original visual representation of the product's operating model`,
    });
    const head = node("div", { class: "instrument-head" });
    head.append(
      node("span", { class: "instrument-name", text: vertical.experience.instrument.replaceAll("-", " ") }),
      node("span", { class: "instrument-status", text: "Evidence-bound" }),
    );
    const stage = node("div", { class: "instrument-stage", "aria-hidden": "true" });
    const builder = instrumentBuilders[vertical.slug];
    if (builder) builder(stage);
    const caption = node("figcaption", { class: "instrument-caption" });
    caption.append(node("span", { text: vertical.experience.type_voice.replaceAll("-", " ") }), node("strong", { text: "Original SZL composition" }));
    figure.append(head, stage, caption);
    return figure;
  }

  function renderDecisionRibbon(stage) {
    stage.innerHTML = `
      <div class="decision-ribbon">
        <svg class="proof-lattice" viewBox="0 0 100 100" preserveAspectRatio="none">
          <line x1="4" y1="15" x2="96" y2="82"></line><line x1="8" y1="80" x2="92" y2="18"></line>
          <line x1="20" y1="4" x2="70" y2="96"></line><line x1="32" y1="0" x2="94" y2="64"></line>
          <circle cx="16" cy="24" r="2"></circle><circle cx="36" cy="70" r="2"></circle>
          <circle cx="61" cy="31" r="2"></circle><circle cx="83" cy="66" r="2"></circle>
        </svg>
        <div class="ribbon-track"></div>
        <div class="ribbon-steps">
          <div class="ribbon-step"><span class="ribbon-step-dot"></span><strong>Signal</strong></div>
          <div class="ribbon-step"><span class="ribbon-step-dot"></span><strong>Proposal</strong></div>
          <div class="ribbon-step"><span class="ribbon-step-dot"></span><strong>Policy</strong></div>
          <div class="ribbon-step"><span class="ribbon-step-dot"></span><strong>Human bind</strong></div>
          <div class="ribbon-step"><span class="ribbon-step-dot"></span><strong>Verify</strong></div>
        </div>
      </div>`;
  }

  function renderTheaterMap(stage) {
    stage.innerHTML = `
      <div class="theater-map">
        <div class="radar-core"><span class="radar-axis-x"></span><span class="radar-axis-y"></span><span class="radar-sweep"></span>
          <i class="track track-1"></i><i class="track track-2"></i><i class="track track-3"></i><i class="track track-4"></i>
        </div>
        <div class="orbit-mark"></div>
      </div>`;
  }

  function renderSignalWaterfall(stage) {
    stage.innerHTML = `
      <div class="signal-waterfall">
        <div class="signal-streams">
          <div class="signal-stream"><span>Trace</span><i class="signal-bar" style="--signal-size:88%"></i></div>
          <div class="signal-stream"><span>Metric</span><i class="signal-bar" style="--signal-size:64%"></i></div>
          <div class="signal-stream"><span>Log</span><i class="signal-bar" style="--signal-size:76%"></i></div>
          <div class="signal-stream"><span>Cost</span><i class="signal-bar" style="--signal-size:49%"></i></div>
          <div class="signal-stream"><span>SLO</span><i class="signal-bar" style="--signal-size:70%"></i></div>
        </div>
        <div class="outcome-topology">
          <span class="outcome-node">Service</span><span class="outcome-node">Commitment</span>
          <span class="outcome-node">Owner</span><span class="outcome-node">Outcome</span>
        </div>
      </div>`;
  }

  function renderExposureGraph(stage) {
    stage.innerHTML = `
      <div class="exposure-field">
        <svg class="exposure-lines" viewBox="0 0 100 100" preserveAspectRatio="none">
          <line x1="18" y1="23" x2="49" y2="16"></line><line x1="49" y1="16" x2="78" y2="36"></line>
          <line x1="18" y1="23" x2="31" y2="66"></line><line x1="31" y1="66" x2="66" y2="73"></line>
          <line x1="78" y1="36" x2="66" y2="73"></line><path d="M18,23 C42,42 48,58 66,73"></path>
        </svg>
        <span class="exposure-node n1">Identity</span><span class="exposure-node n2">Asset</span>
        <span class="exposure-node n3 crown">Crown data</span><span class="exposure-node n4">Exploit</span>
        <span class="exposure-node n5">Control</span><span class="prism-beam"></span>
      </div>`;
  }

  function renderParcelStack(stage) {
    stage.innerHTML = `
      <div class="parcel-scene">
        <div class="parcel-stack"><span class="parcel-layer"></span><span class="parcel-layer"></span><span class="parcel-layer"></span><span class="parcel-layer"><i class="parcel-gridline"></i><i class="parcel-pin"></i></span></div>
        <div class="terrain-ledger"><span>Parcel</span><span>Ownership</span><span>Constraint</span><span>Scenario</span></div>
      </div>`;
  }

  function renderResearchTerminal(stage) {
    stage.innerHTML = `
      <div class="research-terminal">
        <div class="market-board">
          <div class="thesis-tape">
            <div class="terminal-row"><span>10-K</span><strong>Revenue quality</strong><em>+0.71</em></div>
            <div class="terminal-row"><span>8-K</span><strong>Guidance delta</strong><em>+0.34</em></div>
            <div class="terminal-row negative"><span>Macro</span><strong>Rate sensitivity</strong><em>-0.42</em></div>
            <div class="terminal-row"><span>Risk</span><strong>Concentration</strong><em>0.58</em></div>
            <div class="mini-chart"><div class="mini-chart-bars"><span style="--bar:38%"></span><span style="--bar:55%"></span><span style="--bar:46%"></span><span style="--bar:74%"></span><span style="--bar:68%"></span><span style="--bar:88%"></span><span style="--bar:61%"></span></div></div>
          </div>
          <div class="evidence-tape"><h4>Disconfirming evidence</h4><ul><li>Assumption freshness</li><li>Counterparty concentration</li><li>Policy regime change</li><li>Filing restatement</li></ul></div>
        </div>
        <div class="terminal-command">bind thesis to exact filing revision<span class="terminal-cursor"></span></div>
      </div>`;
  }

  function renderCitationRail(stage) {
    stage.innerHTML = `
      <div class="citation-scene">
        <div class="citation-rail"><span class="citation-mark">Authority</span><span class="citation-mark">Fact</span><span class="citation-mark">Issue</span><span class="citation-mark">Decision</span></div>
        <div class="matter-stack">
          <div class="authority-card"><i></i><strong>Controlling authority</strong><small>bound citation</small></div>
          <div class="authority-card"><i></i><strong>Disputed fact record</strong><small>human review</small></div>
          <div class="authority-card"><i></i><strong>Deadline computation</strong><small>jurisdiction scoped</small></div>
          <div class="chronology-dots"><span></span><span></span><span></span><span></span><span></span></div>
        </div>
      </div>`;
  }

  function renderOrganBody(stage) {
    stage.innerHTML = `
      <div class="anatomy-scene">
        <svg class="body-outline" viewBox="0 0 220 360"><path d="M110 18c30 0 45 21 45 48 0 21-9 36-19 46 25 15 47 43 52 82l12 104-39 8-18-87-4 122H81l-4-122-18 87-39-8 12-104c5-39 27-67 52-82-10-10-19-25-19-46 0-27 15-48 45-48Z"></path></svg>
        <svg class="synapse-lines" viewBox="0 0 100 100" preserveAspectRatio="none"><path d="M50,15 C45,24 50,31 50,38"></path><path d="M50,38 C40,44 32,49 28,57"></path><path d="M50,38 C60,44 68,49 72,57"></path><path d="M28,57 C36,66 44,72 50,79"></path><path d="M72,57 C64,66 56,72 50,79"></path></svg>
        <span class="organ-node">Yuyay<br>brain</span><span class="organ-node heart">Sonqo<br>heart</span><span class="organ-node">Yawar<br>evidence</span><span class="organ-node">Willay<br>signal</span><span class="organ-node">Tullu<br>policy</span><i class="organ-pulse"></i>
      </div>`;
  }

  function renderBindingsSection(vertical) {
    const section = node("section", { class: "container vertical-section", id: "bindings" });
    section.append(node("div", { class: "section-heading" }, [
      node("div", {}, [
        node("p", { class: "section-kicker", text: "Model and kernel edge" }),
        node("h2", { class: "section-title", text: "Use intelligence as a routed instrument, never as authority." }),
      ]),
      node("p", {
        class: "section-lede",
        text: "Models are assigned narrow proposal roles. Kernels normalize, meter, check invariants, and hard-deny prohibited classes. Every route remains inspectable and human-bound.",
      }),
    ]));

    const layout = node("div", { class: "binding-layout" });
    layout.append(renderBindingPanel("Governed models", "Proposal, extraction, planning, and explanation roles.", vertical.models, "model"));
    layout.append(renderBindingPanel("Portable kernels", "Deterministic checks and bounded computation around model output.", vertical.kernels, "kernel"));
    section.append(layout);
    return section;
  }

  function renderBindingPanel(title, description, rows, kind) {
    const panel = node("article", { class: "binding-panel" });
    panel.append(node("div", { class: "panel-head" }, [node("div", {}, [node("h3", { text: title }), node("p", { text: description })]), chip(`${rows.length} bound`)]));
    const list = node("ul", { class: "panel-body binding-list" });
    for (const row of rows) {
      const item = node("li", { class: "binding-item" });
      item.append(
        node("div", { class: "binding-item-top" }, [
          node("strong", { text: row.id }),
          node("span", { class: "binding-kind", text: kind }),
        ]),
        node("p", { text: titleCase(row.role.replaceAll("-", " ")) }),
      );
      if (row.execution) item.append(chip(row.execution.replaceAll("_", " ")));
      list.append(item);
    }
    panel.append(list);
    return panel;
  }

  function renderSourcesSection(vertical) {
    const section = node("section", { class: "container vertical-section", id: "sources" });
    section.append(node("div", { class: "section-heading" }, [
      node("div", {}, [
        node("p", { class: "section-kicker", text: "Official-source fabric" }),
        node("h2", { class: "section-title", text: "Freshness and provenance stay separate from model confidence." }),
      ]),
      node("p", {
        class: "section-lede",
        text: "The reference runtime permits only fixed HTTPS hosts, rejects off-list redirects, bounds response size and time, and labels historical or operator-connected sources honestly.",
      }),
    ]));

    const layout = node("div", { class: "source-layout" });
    const sourcePanel = node("article", { class: "source-panel" });
    sourcePanel.append(node("div", { class: "panel-head" }, [node("div", {}, [node("h3", { text: "Source contracts" }), node("p", { text: "Inputs this vertical is allowed to observe." })]), chip(`${vertical.sources.length} sources`)]));
    const list = node("ul", { class: "panel-body source-list" });
    for (const source of vertical.sources) {
      const item = node("li", { class: "source-item" });
      item.append(
        node("div", { class: "source-item-top" }, [node("strong", { text: source.id }), node("span", { class: "source-mode", text: source.freshness.replaceAll("_", " ") })]),
        node("p", { text: source.purpose }),
        node("span", { class: "source-host", text: `${source.host} · ${source.mode.replaceAll("_", " ")}` }),
      );
      list.append(item);
    }
    sourcePanel.append(list);

    const snapshotPanel = renderSnapshotPanel(vertical);
    layout.append(sourcePanel, snapshotPanel);
    section.append(layout);
    return section;
  }

  function renderSnapshotPanel(vertical) {
    const panel = node("article", { class: "snapshot-panel" });
    const stateChip = chip("Not sampled", "PARTIAL");
    panel.append(node("div", { class: "panel-head" }, [node("div", {}, [node("h3", { text: "Bounded live snapshot" }), node("p", { text: snapshotDescription(vertical.slug) })]), stateChip]));
    const body = node("div", { class: "panel-body" });
    const controls = node("div", { class: "snapshot-controls" });
    const fields = snapshotFields(vertical.slug);
    for (const field of fields) controls.append(field.wrapper);
    const run = button("Fetch official snapshot", "button button-accent");
    controls.append(run);
    const output = node("pre", { class: "snapshot-output", text: "No source has been queried from this page." });
    const toolbar = node("div", { class: "output-toolbar" });
    const useEvidence = button("Use as proposal evidence", "button");
    useEvidence.disabled = true;
    toolbar.append(node("span", { class: "output-note", text: "HTTP reachability is not readiness or truth." }), useEvidence);
    body.append(controls, output, toolbar);
    panel.append(body);

    run.addEventListener("click", async () => {
      run.disabled = true;
      useEvidence.disabled = true;
      run.textContent = "Fetching…";
      stateChip.textContent = "Fetching";
      stateChip.dataset.state = "PARTIAL";
      output.textContent = "Contacting the fixed source contract…";
      const params = new URLSearchParams();
      for (const field of fields) {
        const value = field.input.value.trim();
        if (value) params.set(field.name, value);
      }
      try {
        const suffix = params.toString() ? `?${params.toString()}` : "";
        const snapshot = await fetchJson(`/api/v1/verticals/${vertical.slug}/snapshot${suffix}`, { timeout: 15000 });
        state.currentSnapshot = snapshot;
        stateChip.textContent = snapshot.state.replaceAll("_", " ");
        stateChip.dataset.state = snapshot.state;
        output.textContent = JSON.stringify(snapshot, null, 2);
        useEvidence.disabled = false;
      } catch (error) {
        state.currentSnapshot = null;
        const code = error.payload?.error || "ERROR";
        stateChip.textContent = code.replaceAll("_", " ");
        stateChip.dataset.state = code === "CONFIGURATION_REQUIRED" ? "CONFIGURATION_REQUIRED" : "ERROR";
        output.textContent = JSON.stringify(error.payload || { error: code, message: error.message }, null, 2);
      } finally {
        run.disabled = false;
        run.textContent = "Fetch official snapshot";
      }
    });

    useEvidence.addEventListener("click", () => {
      if (!state.currentSnapshot) return;
      const snapshot = state.currentSnapshot;
      const evidence = [{
        source: snapshot.source,
        claim: `${vertical.name} official-source snapshot reported state ${snapshot.state}.`,
        uri: snapshot.source_url || `/api/v1/verticals/${vertical.slug}/snapshot`,
        observed_at: snapshot.observed_at,
        sha256: snapshot.receipt_sha256,
      }];
      const textarea = document.querySelector("[data-evidence-input]");
      if (textarea) {
        textarea.value = JSON.stringify(evidence, null, 2);
        textarea.dispatchEvent(new Event("input", { bubbles: true }));
        document.querySelector("#workbench")?.scrollIntoView({ behavior: prefersReducedMotion() ? "auto" : "smooth" });
        showToast("Snapshot bound into the proposal evidence field.");
      }
    });

    return panel;
  }

  function snapshotDescription(slug) {
    const descriptions = {
      a11oy: "Inspect the local source-bound vertical registry and authority contract.",
      killinchu: "Inspect the historical NOAA/USCG planning-data boundary. No live tactical feed is claimed.",
      lyte: "Inspect recent GitHub Actions execution telemetry for a public SZL repository.",
      sentra: "Read the current official CISA Known Exploited Vulnerabilities catalog.",
      terra: "Read a bounded sample of official NYC PLUTO parcel records.",
      puriq: "Read official SEC submissions metadata. The server must identify its operator to the SEC.",
      prism: "Search current Federal Register documents through the official public API.",
      anatomy: "Inspect the Python process, source revision, registry digest, and authority state.",
    };
    return descriptions[slug] || "Inspect the bound source contract.";
  }

  function snapshotFields(slug) {
    const fields = [];
    if (slug === "lyte") fields.push(formField("Repository", "repo", "szl-command-lab", "Simple repository name under szl-holdings."));
    if (slug === "terra") fields.push(formField("Sample limit", "limit", "12", "Bounded from 1 to 25 records.", "number"));
    if (slug === "puriq") fields.push(formField("SEC CIK", "cik", "0000320193", "One to ten digits. SEC_USER_AGENT is required on the server."));
    if (slug === "prism") fields.push(formField("Search term", "term", "artificial intelligence", "Optional; maximum 80 characters."));
    return fields;
  }

  function formField(labelText, name, defaultValue, help, type = "text") {
    const id = `snapshot-${name}`;
    const wrapper = node("label", { class: "field", for: id });
    const input = node("input", { class: "text-field", id, name, type, value: defaultValue, autocomplete: "off" });
    wrapper.append(node("span", { class: "field-label", text: labelText }), input, node("span", { class: "field-help", text: help }));
    return { wrapper, input, name };
  }

  function renderWorkbench(vertical) {
    const section = node("section", { class: "container vertical-section", id: "workbench" });
    section.append(node("div", { class: "section-heading" }, [
      node("div", {}, [
        node("p", { class: "section-kicker", text: "Governed proposal workbench" }),
        node("h2", { class: "section-title", text: "Turn evidence into a bounded proposal and deterministic receipt." }),
      ]),
      node("p", {
        class: "section-lede",
        text: "This public reference path never executes an external effect. It exposes why a proposal is held, which model and kernel roles were selected, and whether the receipt survives tampering.",
      }),
    ]));

    const layout = node("div", { class: "workbench-layout" });
    const proposalPanel = node("article", { class: "proposal-panel" });
    proposalPanel.append(node("div", { class: "panel-head" }, [node("div", {}, [node("h3", { text: "Compose proposal" }), node("p", { text: "All fields remain local until you submit this form to the Python runtime." })]), chip("No execution") ]));
    const form = node("form", { class: "panel-body form-grid" });

    const objective = node("textarea", {
      class: "textarea-field",
      id: "proposal-objective",
      name: "objective",
      required: "true",
      maxlength: "2000",
      placeholder: objectivePlaceholder(vertical.slug),
    });
    const objectiveField = node("label", { class: "field", for: "proposal-objective" }, [
      node("span", { class: "field-label", text: "Objective" }),
      objective,
      node("span", { class: "field-help", text: "Describe the decision to analyze, not a command to execute." }),
    ]);

    const action = node("input", {
      class: "text-field",
      id: "proposal-action",
      name: "requested_action",
      maxlength: "500",
      value: "review evidence and prepare an operator recommendation",
    });
    const actionField = node("label", { class: "field", for: "proposal-action" }, [
      node("span", { class: "field-label", text: "Requested action class" }),
      action,
      node("span", { class: "field-help", text: "Prohibited or consequential action classes fail closed." }),
    ]);

    const risk = node("input", { class: "range-field", id: "proposal-risk", type: "range", min: "0", max: "1", step: "0.01", value: "0.35" });
    const riskValue = node("output", { class: "range-value", for: "proposal-risk", text: "0.35" });
    risk.addEventListener("input", () => { riskValue.value = Number(risk.value).toFixed(2); riskValue.textContent = riskValue.value; });
    const riskField = node("div", { class: "field" }, [
      node("label", { class: "field-label", for: "proposal-risk", text: "Estimated risk" }),
      node("div", { class: "range-wrap" }, [risk, riskValue]),
      node("span", { class: "field-help", text: "At 0.65 or above, the reference policy adds an elevated-risk hold." }),
    ]);

    const evidence = node("textarea", {
      class: "textarea-field",
      id: "proposal-evidence",
      name: "evidence",
      dataset: { evidenceInput: "" },
      placeholder: '[\n  {\n    "source": "source-id",\n    "claim": "Observed fact",\n    "uri": "https://…",\n    "observed_at": "2026-09-04T00:00:00Z"\n  }\n]',
    });
    const evidenceField = node("label", { class: "field", for: "proposal-evidence" }, [
      node("span", { class: "field-label", text: "Evidence JSON" }),
      evidence,
      node("span", { class: "field-help", text: "Up to twelve objects. Use the source snapshot above to bind a receipted observation." }),
    ]);

    const approval = node("input", { id: "proposal-approval", type: "checkbox", checked: false });
    const approvalField = node("label", { class: "checkbox-field", for: "proposal-approval" }, [
      approval,
      node("span", { class: "checkbox-copy" }, [
        node("strong", { text: "Record a human review signal" }),
        node("small", { text: "This input does not authorize or execute anything. It only satisfies the reference proposal gate." }),
      ]),
    ]);

    const submit = button("Generate governed receipt", "button button-accent", "submit");
    form.append(objectiveField, actionField, riskField, evidenceField, approvalField, submit);
    proposalPanel.append(form);

    const receiptPanel = node("article", { class: "receipt-panel" });
    const receiptState = chip("Awaiting proposal", "PARTIAL");
    receiptPanel.append(node("div", { class: "panel-head" }, [node("div", {}, [node("h3", { text: "Decision receipt" }), node("p", { text: "Canonical JSON integrity, route disclosure, policy holds, and execution boundary." })]), receiptState]));
    const receiptBody = node("div", { class: "panel-body" });
    const summary = node("div", { class: "receipt-summary" });
    const receiptOutput = node("pre", { class: "receipt-output", text: "Submit an evidence-bound objective to generate a receipt." });
    const verifyOutput = node("pre", { class: "verify-output", text: "Verification has not run." });
    const tools = node("div", { class: "output-toolbar" });
    const copyButton = button("Copy receipt", "button");
    const verifyButton = button("Verify integrity", "button");
    copyButton.disabled = true;
    verifyButton.disabled = true;
    tools.append(node("span", { class: "output-note", text: "Integrity is not truth, safety, performance, compliance, or authorization." }), node("div", { class: "action-row" }, [copyButton, verifyButton]));
    receiptBody.append(summary, receiptOutput, tools, node("p", { class: "field-label", text: "Verifier" }), verifyOutput);
    receiptPanel.append(receiptBody);

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      submit.disabled = true;
      submit.textContent = "Evaluating…";
      receiptState.textContent = "Evaluating";
      receiptState.dataset.state = "PARTIAL";
      summary.replaceChildren();
      receiptOutput.textContent = "Applying source, evidence, risk, and prohibited-action gates…";
      verifyOutput.textContent = "Verification has not run.";
      try {
        let parsedEvidence = [];
        const rawEvidence = evidence.value.trim();
        if (rawEvidence) {
          try {
            parsedEvidence = JSON.parse(rawEvidence);
          } catch {
            throw new Error("Evidence must be valid JSON before the proposal can be evaluated.");
          }
        }
        const payload = {
          vertical: vertical.slug,
          objective: objective.value,
          requested_action: action.value,
          risk: Number(risk.value),
          evidence: parsedEvidence,
          human_approved: approval.checked,
        };
        const receipt = await fetchJson("/api/v1/decision", { method: "POST", body: payload });
        state.currentReceipt = receipt;
        receiptState.textContent = receipt.state.replaceAll("_", " ");
        receiptState.dataset.state = receipt.state;
        renderReceiptSummary(summary, receipt);
        receiptOutput.textContent = JSON.stringify(receipt, null, 2);
        copyButton.disabled = false;
        verifyButton.disabled = false;
      } catch (error) {
        state.currentReceipt = null;
        receiptState.textContent = "ERROR";
        receiptState.dataset.state = "ERROR";
        receiptOutput.textContent = JSON.stringify(error.payload || { error: "INVALID_REQUEST", message: error.message }, null, 2);
        copyButton.disabled = true;
        verifyButton.disabled = true;
      } finally {
        submit.disabled = false;
        submit.textContent = "Generate governed receipt";
      }
    });

    copyButton.addEventListener("click", async () => {
      if (!state.currentReceipt) return;
      try {
        await navigator.clipboard.writeText(JSON.stringify(state.currentReceipt, null, 2));
        showToast("Receipt copied.");
      } catch {
        showToast("Clipboard access is unavailable in this browser.");
      }
    });

    verifyButton.addEventListener("click", async () => {
      if (!state.currentReceipt) return;
      verifyButton.disabled = true;
      verifyButton.textContent = "Verifying…";
      try {
        const { receipt_sha256: digest, ...receipt } = state.currentReceipt;
        const verification = await fetchJson("/api/v1/verify", {
          method: "POST",
          body: { receipt, receipt_sha256: digest },
        });
        verifyOutput.textContent = JSON.stringify(verification, null, 2);
        showToast(verification.valid ? "Receipt integrity verified." : "Receipt integrity failed.");
      } catch (error) {
        verifyOutput.textContent = JSON.stringify(error.payload || { error: "VERIFY_ERROR", message: error.message }, null, 2);
      } finally {
        verifyButton.disabled = false;
        verifyButton.textContent = "Verify integrity";
      }
    });

    layout.append(proposalPanel, receiptPanel);
    section.append(layout);
    return section;
  }

  function renderReceiptSummary(container, receipt) {
    const stateRow = node("div", { class: "receipt-state" });
    stateRow.append(chip(receipt.state.replaceAll("_", " "), receipt.state), chip(`${receipt.proposal?.evidence_count || 0} evidence item(s)`));
    container.append(stateRow, node("p", { class: "receipt-digest", text: `sha256 ${receipt.receipt_sha256}` }));
    if (receipt.blocks?.length) {
      const list = node("ul", { class: "receipt-blocks" });
      receipt.blocks.forEach((item) => list.append(node("li", { text: item.replaceAll("_", " ") })));
      container.append(list);
    }
  }

  function objectivePlaceholder(slug) {
    const values = {
      a11oy: "Assess whether the attached evidence supports a bounded operator decision and identify unresolved policy gates.",
      killinchu: "Assess the maritime evidence for an anomalous track and prepare a non-actuating operator recommendation.",
      lyte: "Trace a failed workflow signal to its affected service commitment, owner, and next human decision.",
      sentra: "Prioritize the attached known-exploited vulnerability evidence against business criticality and compensating controls.",
      terra: "Build a parcel diligence hypothesis from the attached public record and list unresolved ownership, hazard, and regulatory evidence.",
      puriq: "Construct a falsifiable research thesis from the filing evidence and name the strongest disconfirming evidence to monitor.",
      prism: "Map the attached authority to the relevant issue, fact record, jurisdiction, and unresolved human review step.",
      anatomy: "Identify the degraded system organ, trace downstream decision impact, and state why the body should hold or fail closed.",
    };
    return values[slug] || "Describe the evidence-bound decision to analyze.";
  }

  function renderBoundary(vertical) {
    const band = node("section", { class: "boundary-band" });
    const grid = node("div", { class: "container boundary-grid" });
    grid.append(
      node("div", {}, [
        node("p", { class: "section-kicker", text: "Authority boundary" }),
        node("p", { class: "boundary-statement", html: "The model proposes.<br>The kernel checks.<br><em>The human binds.</em>" }),
      ]),
    );
    const panel = node("article", { class: "boundary-panel" });
    panel.append(node("div", { class: "panel-head" }, [node("div", {}, [node("h3", { text: `What ${vertical.name} refuses` }), node("p", { text: "Public product boundaries are features, not footnotes." })]), chip("Fail closed") ]));
    const list = node("ul", { class: "panel-body boundary-list" });
    for (const item of vertical.prohibited) list.append(node("li", { class: "boundary-item", text: titleCase(item) }));
    list.append(
      node("li", { class: "boundary-item", text: "A running service, model output, formula, signature, or HTTP 200 never grants consequential authority." }),
      node("li", { class: "boundary-item", text: "Lambda uniqueness remains Conjecture 1 — open. Public effectors remain disabled." }),
    );
    panel.append(list);
    grid.append(panel);
    band.append(grid);
    return band;
  }

  function titleCase(value) {
    const text = String(value || "").replaceAll("_", " ").replaceAll("-", " ");
    return text.charAt(0).toUpperCase() + text.slice(1);
  }

  function edgeExplanation(item) {
    const value = item.toLowerCase();
    if (value.includes("ontology")) return "Signals, proposals, policies, approvals, actions, and outcomes use the same reconstructable object model.";
    if (value.includes("source-bound")) return "Every proposal can retain its input digest, source revision, freshness state, and deterministic receipt.";
    if (value.includes("anatomy")) return "A degraded memory, evidence, policy, or execution organ is visible and can fail the decision body closed.";
    if (value.includes("second-brain")) return "Observation memory is scoped and bounded instead of silently becoming global model memory.";
    if (value.includes("kernel")) return "Portable checks surround model output so governance is not dependent on one provider or prompt.";
    if (value.includes("human")) return "Consequential authority remains outside the proposer and requires an explicit operator-owned binding path.";
    if (value.includes("freshness")) return "A confident model cannot upgrade stale, partial, or unavailable evidence into current fact.";
    return "The capability compounds across the estate while preserving each vertical's distinct operating boundary.";
  }

  function mixHex(a, b, ratio) {
    const parse = (value) => {
      const normalized = value.replace("#", "");
      return [0, 2, 4].map((index) => Number.parseInt(normalized.slice(index, index + 2), 16));
    };
    try {
      const left = parse(a);
      const right = parse(b);
      const result = left.map((value, index) => Math.round(value * ratio + right[index] * (1 - ratio)));
      return `#${result.map((value) => value.toString(16).padStart(2, "0")).join("")}`;
    } catch {
      return a;
    }
  }

  async function init() {
    registerGlobalEvents();
    try {
      const registry = await fetchJson("/api/v1/verticals", { timeout: 10000 });
      if (!registry || !Array.isArray(registry.verticals) || registry.verticals.length !== 8) {
        throw new Error("The vertical registry did not return the eight-system contract.");
      }
      state.registry = registry;
      renderNavigation();
      boot.hidden = true;
      renderRoute();
    } catch (error) {
      boot.hidden = true;
      const shell = node("div", { class: "error-state" });
      const card = node("section", { class: "error-card" });
      card.append(
        node("p", { class: "eyebrow", text: "Fail-closed startup" }),
        node("h1", { text: "The vertical registry is unavailable." }),
        node("p", { text: error.message || "The public portfolio cannot be rendered without its source-bound registry." }),
      );
      const retry = button("Retry", "button button-primary");
      retry.addEventListener("click", () => window.location.reload());
      card.append(retry);
      shell.append(card);
      appRoot.replaceChildren(shell);
    }
  }

  init();
})();
