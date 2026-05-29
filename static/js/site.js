const root = document.documentElement;
const body = document.body;
const siteHeader = document.querySelector("[data-site-header]");
const toggleButton = document.querySelector("[data-theme-toggle]");
const toggleLabel = document.querySelector(".theme-toggle-label");
const storedTheme = localStorage.getItem("vortex-theme");
const navToggle = document.querySelector("[data-nav-toggle]");
const navPanel = document.querySelector("[data-nav-panel]");
const brandMenuShell = document.querySelector("[data-brand-menu-shell]");
const brandMenuToggle = document.querySelector("[data-brand-menu-toggle]");
const brandMenu = document.querySelector("[data-brand-menu]");
const brandEmblem = brandMenuToggle?.querySelector(".brand-emblem");
const revealElements = document.querySelectorAll(".reveal-on-scroll");
const imageInput = document.querySelector("#id_primary_image");
const previewImage = document.querySelector("[data-image-preview-target]");
const previewPlaceholder = document.querySelector("[data-image-preview-placeholder]");
const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
const finePointer = window.matchMedia("(pointer: fine)");
const glowState = new WeakMap();
let themeTransitionTimeout;
let lastHeaderScrollY = window.scrollY;

const elevatedSurfaceSelector = [
  ".card-shell",
  ".section-shell",
  ".info-card",
  ".auth-card-main",
  ".auth-card-side",
  ".product-card",
  ".admin-sidebar",
  ".admin-content",
  ".form-panel",
  ".flash-message",
  ".empty-panel",
  ".metric-card",
  ".gallery-item",
  ".table-shell",
  ".status-panel",
  ".detail-gallery",
].join(", ");

const subtleHoverSelector = [
  ".product-card",
  ".info-card",
  ".metric-card",
  ".auth-card-main",
  ".auth-card-side",
  ".form-panel",
  ".empty-panel",
  ".gallery-item",
  ".table-shell",
  ".detail-gallery",
].join(", ");

const interactiveGlowSelector = [
  ".card-shell",
  ".section-shell",
  ".info-card",
  ".auth-card-main",
  ".auth-card-side",
  ".product-card",
  ".admin-sidebar",
  ".admin-content",
  ".form-panel",
  ".empty-panel",
  ".metric-card",
  ".gallery-item",
  ".table-shell",
  ".status-panel",
  ".detail-gallery",
].join(", ");

if (storedTheme) {
  root.dataset.theme = storedTheme;
}

function syncThemeLabel() {
  if (!toggleButton || !toggleLabel) {
    return;
  }

  const isLight = root.dataset.theme === "light";
  toggleLabel.textContent = isLight ? toggleButton.dataset.lightLabel : toggleButton.dataset.darkLabel;
}

function animateThemeTransition() {
  root.classList.add("theme-transition");
  window.clearTimeout(themeTransitionTimeout);
  themeTransitionTimeout = window.setTimeout(() => {
    root.classList.remove("theme-transition");
  }, 420);
}

function syncHeaderMetrics() {
  if (!siteHeader) {
    return;
  }

  root.style.setProperty("--site-header-height", `${siteHeader.offsetHeight}px`);
}

function syncHeaderState() {
  if (!siteHeader) {
    return;
  }

  const currentScrollY = window.scrollY;
  const isScrollingDown = currentScrollY > lastHeaderScrollY + 1;
  const isScrollingUp = currentScrollY < lastHeaderScrollY - 1;
  const isBrandMenuOpen = brandMenuShell?.classList.contains("is-open");

  siteHeader.classList.toggle("is-scrolled", currentScrollY > 12);

  if (currentScrollY <= 32 || isScrollingUp || isBrandMenuOpen || siteHeader.matches(":focus-within")) {
    siteHeader.classList.remove("is-hidden");
  } else if (currentScrollY > 110 && isScrollingDown) {
    siteHeader.classList.add("is-hidden");
  }

  lastHeaderScrollY = currentScrollY;
}

function assignStaggerIndices(selector) {
  document.querySelectorAll(selector).forEach((element, index) => {
    element.style.setProperty("--stagger-index", String(index));
  });
}

function addUtilityClasses(selector, ...classes) {
  document.querySelectorAll(selector).forEach((element) => {
    classes.forEach((className) => element.classList.add(className));
  });
}

function supportsInteractiveGlow() {
  return finePointer.matches && !prefersReducedMotion.matches;
}

function primeGlowSurface(element) {
  if (!element.querySelector(":scope > .glow-layer")) {
    const glowLayer = document.createElement("span");
    glowLayer.className = "glow-layer";
    glowLayer.setAttribute("aria-hidden", "true");
    element.append(glowLayer);
  }

  element.style.setProperty("--glow-x", "50%");
  element.style.setProperty("--glow-y", "50%");

  if (element.dataset.glowBound === "true") {
    return;
  }

  element.dataset.glowBound = "true";
  const state = { frame: 0, clientX: 0, clientY: 0 };
  glowState.set(element, state);

  const updateGlow = () => {
    state.frame = 0;
    const rect = element.getBoundingClientRect();
    const x = ((state.clientX - rect.left) / rect.width) * 100;
    const y = ((state.clientY - rect.top) / rect.height) * 100;
    element.style.setProperty("--glow-x", `${Math.max(0, Math.min(100, x))}%`);
    element.style.setProperty("--glow-y", `${Math.max(0, Math.min(100, y))}%`);
  };

  element.addEventListener("pointerenter", (event) => {
    if (!supportsInteractiveGlow() || event.pointerType !== "mouse") {
      return;
    }

    state.clientX = event.clientX;
    state.clientY = event.clientY;
    element.classList.add("is-glow-active");

    if (!state.frame) {
      state.frame = window.requestAnimationFrame(updateGlow);
    }
  });

  element.addEventListener("pointermove", (event) => {
    if (!supportsInteractiveGlow() || event.pointerType !== "mouse") {
      return;
    }

    state.clientX = event.clientX;
    state.clientY = event.clientY;

    if (!state.frame) {
      state.frame = window.requestAnimationFrame(updateGlow);
    }
  });

  element.addEventListener("pointerleave", () => {
    element.classList.remove("is-glow-active");
    element.style.setProperty("--glow-x", "50%");
    element.style.setProperty("--glow-y", "50%");

    if (state.frame) {
      window.cancelAnimationFrame(state.frame);
      state.frame = 0;
    }
  });
}

function initializeInteractiveGlow() {
  document.querySelectorAll(".interactive-glow:not(.glow-exclude)").forEach((element) => {
    primeGlowSurface(element);

    if (!supportsInteractiveGlow()) {
      element.classList.remove("is-glow-active");
      element.style.setProperty("--glow-x", "50%");
      element.style.setProperty("--glow-y", "50%");
    }
  });
}

function initializeBuildGallery() {
  document.querySelectorAll("[data-build-gallery]").forEach((gallery) => {
    if (gallery.dataset.galleryBound === "true") {
      return;
    }

    const mainImage = gallery.querySelector("[data-gallery-main-image]");
    const modal = gallery.querySelector("[data-gallery-modal]");
    const modalImage = gallery.querySelector("[data-gallery-modal-image]");
    const modalViewport = gallery.querySelector("[data-gallery-zoom-viewport]");
    const counter = gallery.querySelector("[data-gallery-counter]");
    const openButton = gallery.querySelector("[data-gallery-open]");
    const prevButton = gallery.querySelector("[data-gallery-prev]");
    const nextButton = gallery.querySelector("[data-gallery-next]");
    const inlinePrevButton = gallery.querySelector("[data-gallery-prev-inline]");
    const inlineNextButton = gallery.querySelector("[data-gallery-next-inline]");
    const inlineCounter = gallery.querySelector("[data-gallery-inline-counter]");
    const closeButtons = gallery.querySelectorAll("[data-gallery-close]");
    const galleryItems = Array.from(gallery.querySelectorAll("[data-gallery-item]"));
    const thumbButtons = Array.from(gallery.querySelectorAll("[data-gallery-thumb]"));

    if (!mainImage || !modal || !modalImage) {
      return;
    }

    if (modal.parentElement !== body) {
      body.appendChild(modal);
    }

    const items = galleryItems.length
      ? galleryItems.map((item) => ({
          src: item.dataset.gallerySrc,
          alt: item.dataset.galleryAlt || mainImage.alt,
        }))
      : thumbButtons.length
      ? thumbButtons.map((button) => ({
          src: button.dataset.gallerySrc,
          alt: button.dataset.galleryAlt || mainImage.alt,
        }))
      : [{ src: mainImage.currentSrc || mainImage.src, alt: mainImage.alt }];

    let currentIndex = 0;
    let modalZoom = 1;
    let modalPanX = 0;
    let modalPanY = 0;
    let isPanning = false;
    let panStartX = 0;
    let panStartY = 0;
    let panOriginX = 0;
    let panOriginY = 0;
    let pinchStartDistance = 0;
    let pinchStartZoom = 1;
    gallery.dataset.galleryBound = "true";

    const clamp = (value, minimum, maximum) => Math.max(minimum, Math.min(maximum, value));

    function constrainModalPan() {
      if (!modalViewport || modalZoom <= 1) {
        modalPanX = 0;
        modalPanY = 0;
        return;
      }

      const maxPanX = Math.max(0, (modalImage.offsetWidth * modalZoom - modalViewport.clientWidth) / 2);
      const maxPanY = Math.max(0, (modalImage.offsetHeight * modalZoom - modalViewport.clientHeight) / 2);
      modalPanX = clamp(modalPanX, -maxPanX, maxPanX);
      modalPanY = clamp(modalPanY, -maxPanY, maxPanY);
    }

    function applyModalZoom() {
      constrainModalPan();
      modalImage.style.setProperty("--gallery-scale", modalZoom.toFixed(3));
      modalImage.style.setProperty("--gallery-x", `${modalPanX}px`);
      modalImage.style.setProperty("--gallery-y", `${modalPanY}px`);
      modalImage.classList.toggle("is-zoomed", modalZoom > 1.01);
      modalViewport?.classList.toggle("is-zoomed", modalZoom > 1.01);
    }

    function setModalZoom(nextZoom, originEvent = null) {
      if (!modalViewport) {
        return;
      }

      const previousZoom = modalZoom;
      modalZoom = clamp(nextZoom, 1, 4);

      if (originEvent && previousZoom > 0 && modalZoom !== previousZoom) {
        const rect = modalViewport.getBoundingClientRect();
        const originX = originEvent.clientX - rect.left - rect.width / 2;
        const originY = originEvent.clientY - rect.top - rect.height / 2;
        const ratio = modalZoom / previousZoom;
        modalPanX = originX - (originX - modalPanX) * ratio;
        modalPanY = originY - (originY - modalPanY) * ratio;
      }

      applyModalZoom();
    }

    function resetModalZoom() {
      modalZoom = 1;
      modalPanX = 0;
      modalPanY = 0;
      isPanning = false;
      applyModalZoom();
    }

    function renderGallery(index) {
      currentIndex = (index + items.length) % items.length;
      const currentItem = items[currentIndex];

      mainImage.src = currentItem.src;
      mainImage.alt = currentItem.alt;
      modalImage.src = currentItem.src;
      modalImage.alt = currentItem.alt;
      resetModalZoom();

      if (counter) {
        counter.textContent = `${currentIndex + 1} / ${items.length}`;
      }

      if (inlineCounter) {
        inlineCounter.textContent = `${currentIndex + 1} / ${items.length}`;
      }

      thumbButtons.forEach((button, thumbIndex) => {
        button.classList.toggle("is-active", thumbIndex === currentIndex);
      });

      [prevButton, nextButton, inlinePrevButton, inlineNextButton].forEach((button) => {
        if (button) {
          button.disabled = items.length <= 1;
        }
      });
    }

    function openGallery() {
      modal.classList.add("is-open");
      modal.setAttribute("aria-hidden", "false");
      body.classList.add("gallery-open");
      renderGallery(currentIndex);
    }

    function closeGallery() {
      modal.classList.remove("is-open");
      modal.setAttribute("aria-hidden", "true");
      resetModalZoom();
      body.classList.remove("gallery-open");
    }

    openButton?.addEventListener("click", openGallery);

    prevButton?.addEventListener("click", () => {
      renderGallery(currentIndex - 1);
    });

    nextButton?.addEventListener("click", () => {
      renderGallery(currentIndex + 1);
    });

    modalViewport?.addEventListener(
      "wheel",
      (event) => {
        event.preventDefault();
        const zoomFactor = event.deltaY < 0 ? 1.12 : 0.88;
        setModalZoom(modalZoom * zoomFactor, event);
      },
      { passive: false }
    );

    modalViewport?.addEventListener("dblclick", (event) => {
      event.preventDefault();
      setModalZoom(modalZoom > 1.01 ? 1 : 2.2, event);
    });

    modalViewport?.addEventListener("pointerdown", (event) => {
      if (modalZoom <= 1.01 || event.button !== 0) {
        return;
      }

      event.preventDefault();
      isPanning = true;
      panStartX = event.clientX;
      panStartY = event.clientY;
      panOriginX = modalPanX;
      panOriginY = modalPanY;
      modalViewport.setPointerCapture?.(event.pointerId);
      modalViewport.classList.add("is-panning");
    });

    modalViewport?.addEventListener("pointermove", (event) => {
      if (!isPanning) {
        return;
      }

      modalPanX = panOriginX + event.clientX - panStartX;
      modalPanY = panOriginY + event.clientY - panStartY;
      applyModalZoom();
    });

    const stopPanning = (event) => {
      if (!isPanning) {
        return;
      }
      isPanning = false;
      modalViewport?.releasePointerCapture?.(event.pointerId);
      modalViewport?.classList.remove("is-panning");
    };

    modalViewport?.addEventListener("pointerup", stopPanning);
    modalViewport?.addEventListener("pointercancel", stopPanning);
    modalViewport?.addEventListener("lostpointercapture", stopPanning);

    const getTouchDistance = (touches) => Math.hypot(
      touches[0].clientX - touches[1].clientX,
      touches[0].clientY - touches[1].clientY
    );

    modalViewport?.addEventListener(
      "touchstart",
      (event) => {
        if (event.touches.length !== 2) {
          return;
        }
        pinchStartDistance = getTouchDistance(event.touches);
        pinchStartZoom = modalZoom;
      },
      { passive: true }
    );

    modalViewport?.addEventListener(
      "touchmove",
      (event) => {
        if (event.touches.length !== 2 || !pinchStartDistance) {
          return;
        }
        event.preventDefault();
        const nextZoom = pinchStartZoom * (getTouchDistance(event.touches) / pinchStartDistance);
        setModalZoom(nextZoom);
      },
      { passive: false }
    );

    inlinePrevButton?.addEventListener("click", () => {
      renderGallery(currentIndex - 1);
    });

    inlineNextButton?.addEventListener("click", () => {
      renderGallery(currentIndex + 1);
    });

    closeButtons.forEach((button) => {
      button.addEventListener("click", closeGallery);
    });

    thumbButtons.forEach((button, index) => {
      button.addEventListener("click", () => {
        renderGallery(index);
      });
    });

    document.addEventListener("keydown", (event) => {
      if (modal.getAttribute("aria-hidden") !== "false") {
        return;
      }

      if (event.key === "Escape") {
        closeGallery();
      } else if (event.key === "ArrowLeft") {
        renderGallery(currentIndex - 1);
      } else if (event.key === "ArrowRight") {
        renderGallery(currentIndex + 1);
      }
    });

    renderGallery(0);
  });
}

function initializeAdminActivityLog() {
  document.querySelectorAll("[data-admin-activity]").forEach((card) => {
    if (card.dataset.activityBound === "true") {
      return;
    }

    const filterSelect = card.querySelector("[data-admin-activity-filter]");
    const sortSelect = card.querySelector("[data-admin-activity-sort]");
    const rowsContainer = card.querySelector("[data-admin-activity-rows]");
    const rows = Array.from(card.querySelectorAll("[data-admin-activity-row]"));
    const emptyMessage = card.querySelector("[data-admin-activity-empty]");
    const expandButton = card.querySelector("[data-admin-activity-expand]");

    if (!filterSelect || !sortSelect || !rowsContainer) {
      return;
    }

    card.dataset.activityBound = "true";

    function rowMatchesCategory(row, category) {
      if (category === "all") {
        return true;
      }
      return (row.dataset.categories || "").split(" ").includes(category);
    }

    function getTimestamp(row) {
      return Number(row.dataset.timestamp || 0);
    }

    function getActorRank(row) {
      return Number(row.dataset.actorRank || 3);
    }

    function sortRows(visibleRows) {
      const sortMode = sortSelect.value;

      return [...visibleRows].sort((firstRow, secondRow) => {
        if (sortMode === "oldest") {
          return getTimestamp(firstRow) - getTimestamp(secondRow);
        }
        if (sortMode === "importance") {
          return getActorRank(firstRow) - getActorRank(secondRow) || getTimestamp(secondRow) - getTimestamp(firstRow);
        }
        return getTimestamp(secondRow) - getTimestamp(firstRow);
      });
    }

    function refreshActivityRows() {
      const category = filterSelect.value;
      const visibleRows = sortRows(rows.filter((row) => rowMatchesCategory(row, category)));

      rows.forEach((row) => {
        row.hidden = true;
      });

      visibleRows.forEach((row) => {
        row.hidden = false;
        rowsContainer.append(row);
      });

      if (emptyMessage) {
        emptyMessage.hidden = visibleRows.length > 0;
      }
    }

    filterSelect.addEventListener("change", refreshActivityRows);
    sortSelect.addEventListener("change", refreshActivityRows);

    expandButton?.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      card.open = true;
      const isExpanded = card.classList.toggle("is-expanded");
      expandButton.textContent = isExpanded ? expandButton.dataset.expandedLabel : expandButton.dataset.collapsedLabel;
    });

    refreshActivityRows();
  });
}

function initializeAdminSwitcher() {
  document.querySelectorAll("[data-admin-switcher]").forEach((switcher) => {
    if (switcher.dataset.switcherBound === "true") {
      return;
    }

    switcher.dataset.switcherBound = "true";
    const links = switcher.querySelectorAll("a");

    links.forEach((link) => {
      link.addEventListener("click", () => {
        switcher.open = false;
      });
    });

    document.addEventListener("click", (event) => {
      if (!switcher.open) {
        return;
      }
      if (!switcher.contains(event.target)) {
        switcher.open = false;
      }
    });

    switcher.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        switcher.open = false;
      }
    });
  });
}

function initializeBrandMenu() {
  if (!brandMenuShell || !brandMenuToggle || !brandMenu) {
    return;
  }

  const anchorLinks = brandMenu.querySelectorAll("a");

  function spinBrandEmblem() {
    if (!brandEmblem || prefersReducedMotion.matches) {
      return;
    }

    brandEmblem.classList.remove("is-spinning");
    void brandEmblem.offsetWidth;
    brandEmblem.classList.add("is-spinning");
  }

  function setBrandMenuState(isOpen, shouldSpin = false) {
    brandMenuShell.classList.toggle("is-open", isOpen);
    brandMenuToggle.setAttribute("aria-expanded", String(isOpen));
    brandMenu.setAttribute("aria-hidden", String(!isOpen));

    if (isOpen) {
      siteHeader?.classList.remove("is-hidden");
    }

    if (shouldSpin) {
      spinBrandEmblem();
    }
  }

  setBrandMenuState(false);

  brandMenuToggle.addEventListener("click", () => {
    const isOpen = !brandMenuShell.classList.contains("is-open");
    setBrandMenuState(isOpen, true);
  });

  anchorLinks.forEach((link) => {
    link.addEventListener("click", () => {
      setBrandMenuState(false);
    });
  });

  document.addEventListener("click", (event) => {
    if (!brandMenuShell.classList.contains("is-open")) {
      return;
    }

    if (!brandMenuShell.contains(event.target)) {
      setBrandMenuState(false);
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && brandMenuShell.classList.contains("is-open")) {
      setBrandMenuState(false);
    }
  });
}

function initializePasswordVisibility() {
  document.querySelectorAll("[data-password-field]").forEach((field) => {
    if (field.dataset.passwordBound === "true") {
      return;
    }

    const input = field.querySelector("input[type='password']");
    const holdButton = field.querySelector("[data-password-hold]");
    const checkbox = field.querySelector("[data-password-checkbox]");

    if (!input || (!holdButton && !checkbox)) {
      return;
    }

    let isHolding = false;
    field.dataset.passwordBound = "true";

    const syncVisibility = () => {
      const isVisible = isHolding || Boolean(checkbox?.checked);
      input.type = isVisible ? "text" : "password";
      holdButton?.classList.toggle("is-active", isHolding);
      holdButton?.setAttribute("aria-pressed", String(isHolding));
    };

    const stopHolding = () => {
      isHolding = false;
      syncVisibility();
    };

    holdButton?.addEventListener("pointerdown", (event) => {
      event.preventDefault();
      isHolding = true;
      holdButton.setPointerCapture?.(event.pointerId);
      syncVisibility();
      input.focus({ preventScroll: true });
    });

    holdButton?.addEventListener("pointerup", stopHolding);
    holdButton?.addEventListener("pointercancel", stopHolding);
    holdButton?.addEventListener("lostpointercapture", stopHolding);

    holdButton?.addEventListener("keydown", (event) => {
      if (event.key !== " " && event.key !== "Enter") {
        return;
      }
      event.preventDefault();
      isHolding = true;
      syncVisibility();
    });

    holdButton?.addEventListener("keyup", stopHolding);
    holdButton?.addEventListener("blur", stopHolding);
    checkbox?.addEventListener("change", syncVisibility);
    syncVisibility();
  });

  document.querySelectorAll("[data-password-group]").forEach((group) => {
    if (group.dataset.passwordGroupBound === "true") {
      return;
    }

    const checkbox = group.querySelector("[data-password-group-checkbox]");
    const inputs = Array.from(group.querySelectorAll("input[type='password']"));

    if (!checkbox || !inputs.length) {
      return;
    }

    group.dataset.passwordGroupBound = "true";

    const syncGroupVisibility = () => {
      inputs.forEach((input) => {
        input.type = checkbox.checked ? "text" : "password";
      });
    };

    checkbox.addEventListener("change", syncGroupVisibility);
    syncGroupVisibility();
  });
}

function initializeCatalogRanges() {
  document.querySelectorAll(".range-input-row input[type='range']").forEach((input) => {
    if (input.dataset.rangeBound === "true") {
      return;
    }

    const row = input.closest(".range-input-row");
    const numberInput = row?.querySelector("[data-range-number]");
    const output = row?.querySelector("[data-range-output]");

    if (!row || !numberInput) {
      return;
    }

    input.dataset.rangeBound = "true";
    const minimum = Number(input.min || numberInput.min || 0);
    const maximum = Number(input.max || numberInput.max || input.value || 0);
    const unit = output?.dataset.rangeUnit || "";

    const clampValue = (value) => {
      const numericValue = Number(value);
      if (!Number.isFinite(numericValue)) {
        return Number(input.value || minimum);
      }
      return Math.max(minimum, Math.min(maximum, numericValue));
    };

    const syncRangeOutput = (value = input.value) => {
      const safeValue = clampValue(value);
      input.value = String(safeValue);
      numberInput.value = String(safeValue);
      if (output) {
        output.textContent = `${safeValue}${unit ? ` ${unit}` : ""}`;
      }
    };

    input.addEventListener("input", () => syncRangeOutput(input.value));
    numberInput.addEventListener("input", () => {
      if (numberInput.value === "") {
        return;
      }
      syncRangeOutput(numberInput.value);
    });
    numberInput.addEventListener("change", () => syncRangeOutput(numberInput.value));
    syncRangeOutput();
  });
}

addUtilityClasses(elevatedSurfaceSelector, "elevated-surface", "depth-layer");
addUtilityClasses(subtleHoverSelector, "subtle-hover");
addUtilityClasses(interactiveGlowSelector, "interactive-glow");

syncThemeLabel();
syncHeaderMetrics();
syncHeaderState();
assignStaggerIndices(".hero-metrics .metric-card");
assignStaggerIndices(".product-grid .product-card");
assignStaggerIndices(".trust-grid .info-card");
assignStaggerIndices(".dashboard-overview .info-card");
initializeInteractiveGlow();
initializeBuildGallery();
initializeAdminActivityLog();
initializeAdminSwitcher();
initializeBrandMenu();
initializePasswordVisibility();
initializeCatalogRanges();

if (toggleButton) {
  toggleButton.addEventListener("click", () => {
    animateThemeTransition();
    const nextTheme = root.dataset.theme === "light" ? "dark" : "light";
    root.dataset.theme = nextTheme;
    localStorage.setItem("vortex-theme", nextTheme);
    syncThemeLabel();
  });
}

window.addEventListener("scroll", syncHeaderState, { passive: true });
window.addEventListener("resize", syncHeaderMetrics);

if (navToggle && navPanel) {
  navToggle.addEventListener("click", () => {
    const isOpen = navPanel.classList.toggle("is-open");
    navToggle.setAttribute("aria-expanded", String(isOpen));
  });

  navPanel.querySelectorAll("a, button").forEach((control) => {
    control.addEventListener("click", () => {
      navPanel.classList.remove("is-open");
      navToggle.setAttribute("aria-expanded", "false");
    });
  });
}

if ("IntersectionObserver" in window) {
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) {
          return;
        }

        entry.target.classList.add("is-visible");
        observer.unobserve(entry.target);
      });
    },
    { threshold: 0.14, rootMargin: "0px 0px -40px 0px" }
  );

  revealElements.forEach((element) => observer.observe(element));
} else {
  revealElements.forEach((element) => element.classList.add("is-visible"));
}

if (imageInput && previewImage) {
  imageInput.addEventListener("change", (event) => {
    const [file] = event.target.files || [];
    if (!file) {
      return;
    }

    const reader = new FileReader();
    reader.onload = () => {
      previewImage.src = String(reader.result);
      previewImage.classList.remove("hidden");
      if (previewPlaceholder) {
        previewPlaceholder.classList.add("hidden");
      }
    };
    reader.readAsDataURL(file);
  });
}

[prefersReducedMotion, finePointer].forEach((query) => {
  query.addEventListener("change", () => {
    initializeInteractiveGlow();
  });
});
