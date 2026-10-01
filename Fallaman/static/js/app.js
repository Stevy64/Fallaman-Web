if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker
      .register("/sw.js", { updateViaCache: "none" })
      .then((reg) => {
        reg.update();
      })
      .catch(() => {});
  });
}

let confirmResolver = null;

function settleConfirm(result) {
  const resolve = confirmResolver;
  confirmResolver = null;
  if (resolve) resolve(result);
}

window.FallamanUI = {
  openSheet(id) {
    const sheet = document.getElementById(id);
    const backdrop = document.getElementById("sheet-backdrop");
    if (!sheet || !backdrop) return;
    backdrop.hidden = false;
    requestAnimationFrame(() => {
      backdrop.classList.add("is-open");
      sheet.classList.add("is-open");
      sheet.setAttribute("aria-hidden", "false");
      document.body.classList.add("sheet-open");
    });
  },

  closeSheets() {
    settleConfirm(false);
    const backdrop = document.getElementById("sheet-backdrop");
    document.querySelectorAll(".bottom-sheet.is-open").forEach((sheet) => {
      sheet.classList.remove("is-open");
      sheet.setAttribute("aria-hidden", "true");
    });
    if (backdrop) {
      backdrop.classList.remove("is-open");
      setTimeout(() => {
        backdrop.hidden = true;
      }, 280);
    }
    document.body.classList.remove("sheet-open");
  },

  confirm({
    title = "Confirmer",
    text = "",
    confirmLabel = "Confirmer",
    cancelLabel = "Annuler",
    danger = false,
  } = {}) {
    return new Promise((resolve) => {
      settleConfirm(false);
      const titleEl = document.getElementById("confirm-sheet-title");
      const textEl = document.getElementById("confirm-sheet-text");
      const okBtn = document.getElementById("confirm-sheet-ok");
      const cancelBtn = document.querySelector("#confirm-sheet [data-confirm-cancel]");
      if (!titleEl || !textEl || !okBtn || !cancelBtn) {
        resolve(window.confirm([title, text].filter(Boolean).join("\n\n")));
        return;
      }
      titleEl.textContent = title;
      textEl.textContent = text;
      okBtn.textContent = confirmLabel;
      cancelBtn.textContent = cancelLabel;
      okBtn.classList.toggle("btn-accent", !danger);
      okBtn.classList.toggle("btn-danger", danger);
      confirmResolver = resolve;
      this.openSheet("confirm-sheet");
      okBtn.focus();
    });
  },

  showLoader() {
    showAppLoader();
  },
  hideLoader() {
    hideAppLoader();
  },
};

const FallamanUI = window.FallamanUI;

const appLoader = document.getElementById("app-loader");
let appLoaderCount = 0;
let appLoaderTimer = null;

function showAppLoader() {
  appLoaderCount += 1;
  if (appLoaderTimer || !appLoader) return;
  appLoaderTimer = window.setTimeout(() => {
    appLoaderTimer = null;
    if (appLoaderCount > 0 && appLoader) {
      appLoader.hidden = false;
      appLoader.setAttribute("aria-hidden", "false");
      document.body.classList.add("is-loading");
      appLoader.classList.add("is-open");
    }
  }, 140);
}

function hideAppLoader(force = false) {
  appLoaderCount = force ? 0 : Math.max(0, appLoaderCount - 1);
  if (appLoaderCount > 0) return;
  if (appLoaderTimer) {
    window.clearTimeout(appLoaderTimer);
    appLoaderTimer = null;
  }
  if (appLoader) {
    appLoader.classList.remove("is-open");
    appLoader.hidden = true;
    appLoader.setAttribute("aria-hidden", "true");
  }
  document.body.classList.remove("is-loading");
}

function isHtmxNode(node) {
  if (!(node instanceof Element)) return false;
  return Boolean(
    node.closest("[hx-get], [hx-post], [hx-put], [hx-patch], [hx-delete], [data-hx-get], [data-hx-post]")
  );
}

document.body.addEventListener("htmx:beforeRequest", (event) => {
  const source = event.detail && event.detail.elt;
  if (source && source.closest(".favorite-form")) return;
  if (source && source.closest("[hx-indicator]")) return;
  showAppLoader();
});
document.body.addEventListener("htmx:afterRequest", (event) => {
  hideAppLoader();
  const source = event.detail && event.detail.elt;
  if (source && source.closest("#filter-sheet") && window.FallamanUI) {
    FallamanUI.closeSheets();
  }
});
document.body.addEventListener("htmx:sendError", () => hideAppLoader());
document.body.addEventListener("htmx:responseError", () => hideAppLoader());

document.addEventListener("submit", (event) => {
  const form = event.target;
  if (!(form instanceof HTMLFormElement) || event.defaultPrevented) return;
  if (form.hasAttribute("data-confirm") || isHtmxNode(form)) return;
  showAppLoader();
});

document.addEventListener("click", (event) => {
  if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
    return;
  }
  const link = event.target.closest("a[href]");
  if (!link || isHtmxNode(link) || link.target === "_blank" || link.hasAttribute("download") || link.dataset.sheetOpen || link.dataset.broadcast) {
    return;
  }
  const href = link.getAttribute("href") || "";
  if (!href || href.startsWith("#") || href.startsWith("javascript:") || /^(mailto:|tel:|sms:)/i.test(href)) {
    return;
  }
  try {
    const url = new URL(link.href, window.location.href);
    if (url.origin !== window.location.origin) return;
    if (url.pathname === window.location.pathname && url.search === window.location.search && url.hash) return;
  } catch (err) {
    return;
  }
  showAppLoader();
});

window.addEventListener("pageshow", () => hideAppLoader(true));

document.addEventListener("click", (event) => {
  const openBtn = event.target.closest("[data-sheet-open]");
  if (openBtn) {
    event.preventDefault();
    FallamanUI.openSheet(openBtn.dataset.sheetOpen);
    return;
  }

  const confirmOk = event.target.closest("#confirm-sheet-ok");
  if (confirmOk) {
    event.preventDefault();
    const resolve = confirmResolver;
    confirmResolver = null;
    const backdrop = document.getElementById("sheet-backdrop");
    document.querySelectorAll(".bottom-sheet.is-open").forEach((sheet) => {
      sheet.classList.remove("is-open");
      sheet.setAttribute("aria-hidden", "true");
    });
    if (backdrop) {
      backdrop.classList.remove("is-open");
      setTimeout(() => {
        backdrop.hidden = true;
      }, 280);
    }
    document.body.classList.remove("sheet-open");
    if (resolve) resolve(true);
    return;
  }

  if (
    event.target.id === "sheet-backdrop" ||
    event.target.closest("[data-sheet-close]") ||
    event.target.closest("[data-confirm-cancel]")
  ) {
    FallamanUI.closeSheets();
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") FallamanUI.closeSheets();
});

document.addEventListener("submit", async (event) => {
  const form = event.target;
  if (!(form instanceof HTMLFormElement) || !form.hasAttribute("data-confirm")) return;
  event.preventDefault();
  const ok = await FallamanUI.confirm({
    title: form.dataset.confirmTitle || "Confirmer",
    text: form.dataset.confirm || "",
    confirmLabel: form.dataset.confirmOk || "Confirmer",
    cancelLabel: form.dataset.confirmCancel || "Annuler",
    danger: form.dataset.confirmDanger === "1",
  });
  if (!ok) return;
  form.removeAttribute("data-confirm");
  if (window.FallamanUI.showLoader) window.FallamanUI.showLoader();
  HTMLFormElement.prototype.submit.call(form);
});

document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-share]");
  if (!button) return;
  event.preventDefault();
  const payload = {
    title: button.dataset.title || "Fallaman",
    text: button.dataset.text || "Voir l'annonce sur Fallaman",
    url: window.location.href,
  };
  if (navigator.share) {
    try {
      await navigator.share(payload);
      FallamanUI.closeSheets();
      return;
    } catch (err) {
      if (err.name === "AbortError") return;
    }
  }
  const shareText = `${payload.text}\n${payload.url}`;
  const phone = (button.dataset.whatsapp || "").replace(/\D/g, "");
  if (phone) {
    window.open(
      `https://wa.me/${phone}?text=${encodeURIComponent(shareText)}`,
      "_blank",
      "noopener"
    );
  } else if (navigator.clipboard) {
    try {
      await navigator.clipboard.writeText(shareText);
      const hint = button.querySelector("small");
      if (hint) hint.textContent = "Texte copié !";
    } catch (err) {
      window.prompt("Copiez ce texte :", shareText);
    }
  } else {
    window.prompt("Copiez ce texte :", shareText);
  }
  FallamanUI.closeSheets();
});

document.addEventListener("click", async (event) => {
  const copyBtn = event.target.closest("[data-copy-link]");
  if (!copyBtn) return;
  try {
    await navigator.clipboard.writeText(window.location.href);
    copyBtn.querySelector("small").textContent = "Lien copié !";
    setTimeout(() => FallamanUI.closeSheets(), 700);
  } catch (err) {
    window.prompt("Copiez ce lien :", window.location.href);
  }
});

document.addEventListener("click", (event) => {
  const tab = event.target.closest("[data-tab]");
  if (!tab) return;
  const root = tab.closest(".detail-sheet") || document;
  root.querySelectorAll("[data-tab]").forEach((btn) => {
    btn.classList.toggle("is-active", btn === tab);
    btn.setAttribute("aria-selected", btn === tab ? "true" : "false");
  });
  const desc = document.getElementById("panel-desc");
  const author = document.getElementById("panel-author");
  if (!desc || !author) return;
  const showAuthor = tab.dataset.tab === "author";
  desc.classList.toggle("is-active", !showAuthor);
  author.classList.toggle("is-active", showAuthor);
  desc.hidden = showAuthor;
  author.hidden = !showAuthor;
});

const topbar = document.getElementById("topbar");
if (topbar) {
  const onScroll = () => {
    topbar.classList.toggle("is-scrolled", window.scrollY > 8);
  };
  onScroll();
  window.addEventListener("scroll", onScroll, { passive: true });
}

function csrfToken() {
  const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : "";
}

async function deleteNotificationRow(row) {
  const card = row.querySelector(".notification-card");
  const btn = row.querySelector(".notification-delete-btn");
  const url = (card && card.dataset.deleteUrl) || (btn && btn.dataset.deleteUrl);
  if (!url || row.classList.contains("is-removing")) return;
  row.classList.add("is-removing");
  try {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "X-CSRFToken": csrfToken(),
        "X-Requested-With": "XMLHttpRequest",
      },
      credentials: "same-origin",
    });
    if (!response.ok) throw new Error("delete failed");
    row.style.maxHeight = `${row.scrollHeight}px`;
    requestAnimationFrame(() => {
      row.style.maxHeight = "0px";
      row.style.opacity = "0";
      row.style.marginBottom = "0";
    });
    setTimeout(() => {
      row.remove();
      const list = document.getElementById("notification-list");
      if (list && !list.querySelector(".notification-row")) {
        list.innerHTML = '<div class="empty-state"><p>Pas de notification pour le moment.</p></div>';
      }
    }, 280);
  } catch (err) {
    row.classList.remove("is-removing");
    const surface = row.querySelector(".notification-surface");
    if (surface) surface.style.transform = "";
  }
}

(function initNotificationSwipe() {
  const list = document.getElementById("notification-list");
  if (!list) return;

  function fillBroadcastSheet(data) {
    const titleEl = document.getElementById("broadcast-sheet-title");
    const metaEl = document.getElementById("broadcast-sheet-meta");
    const bodyEl = document.getElementById("broadcast-sheet-body");
    if (!titleEl || !bodyEl) return false;
    titleEl.textContent = data.title || "Message de l'équipe";
    if (metaEl) metaEl.textContent = data.created_at ? `Fallaman · ${data.created_at}` : "Fallaman";
    bodyEl.textContent = "";
    const text = data.body || "";
    if (text) {
      text.split(/\n/).forEach((line, index, arr) => {
        bodyEl.appendChild(document.createTextNode(line));
        if (index < arr.length - 1) bodyEl.appendChild(document.createElement("br"));
      });
    } else {
      bodyEl.textContent = "Aucun détail supplémentaire.";
    }
    return true;
  }

  async function openBroadcastCard(card) {
    const openUrl = card.dataset.openUrl || card.getAttribute("href");
    if (!openUrl || !window.FallamanUI) {
      window.location.href = card.getAttribute("href");
      return;
    }
    try {
      const response = await fetch(openUrl, {
        headers: {
          Accept: "application/json",
          "X-Requested-With": "XMLHttpRequest",
        },
        credentials: "same-origin",
      });
      if (!response.ok) throw new Error("open failed");
      const data = await response.json();
      if (!fillBroadcastSheet(data)) {
        window.location.href = openUrl;
        return;
      }
      card.classList.remove("is-unread");
      FallamanUI.openSheet("broadcast-sheet");
    } catch (err) {
      window.location.href = openUrl;
    }
  }

  list.addEventListener("click", (event) => {
    const btn = event.target.closest(".notification-delete-btn");
    if (btn) {
      event.preventDefault();
      event.stopPropagation();
      const row = btn.closest(".notification-row");
      if (row) deleteNotificationRow(row);
      return;
    }

    const broadcast = event.target.closest(".notification-card[data-broadcast]");
    if (broadcast) {
      event.preventDefault();
      openBroadcastCard(broadcast);
    }
  });

  let startX = 0;
  let startY = 0;
  let currentX = 0;
  let tracking = false;
  let horizontal = null;
  let activeRow = null;
  let activeSurface = null;

  const reset = () => {
    if (activeSurface && !activeRow?.classList.contains("is-removing")) {
      activeSurface.style.transition = "transform .2s ease";
      activeSurface.style.transform = "";
    }
    tracking = false;
    horizontal = null;
    activeRow = null;
    activeSurface = null;
  };

  list.addEventListener(
    "touchstart",
    (event) => {
      const row = event.target.closest(".notification-row");
      if (!row) return;
      const touch = event.changedTouches[0];
      startX = touch.clientX;
      startY = touch.clientY;
      currentX = 0;
      tracking = true;
      horizontal = null;
      activeRow = row;
      activeSurface = row.querySelector(".notification-surface");
      if (activeSurface) activeSurface.style.transition = "none";
    },
    { passive: true }
  );

  list.addEventListener(
    "touchmove",
    (event) => {
      if (!tracking || !activeSurface) return;
      const touch = event.changedTouches[0];
      const dx = touch.clientX - startX;
      const dy = touch.clientY - startY;
      if (horizontal === null) {
        if (Math.abs(dx) < 8 && Math.abs(dy) < 8) return;
        horizontal = Math.abs(dx) > Math.abs(dy);
        if (!horizontal) {
          reset();
          return;
        }
      }
      if (!horizontal) return;
      currentX = Math.min(0, dx);
      activeSurface.style.transform = `translateX(${currentX}px)`;
    },
    { passive: true }
  );

  list.addEventListener(
    "touchend",
    () => {
      if (!tracking || !activeRow || !activeSurface) {
        reset();
        return;
      }
      if (currentX < -88) {
        activeSurface.style.transition = "transform .18s ease";
        activeSurface.style.transform = "translateX(-110%)";
        deleteNotificationRow(activeRow);
        tracking = false;
        horizontal = null;
        activeRow = null;
        activeSurface = null;
        return;
      }
      reset();
    },
    { passive: true }
  );

  list.addEventListener("touchcancel", reset, { passive: true });
})();

function closeAppSelects(exceptWrap) {
  document.querySelectorAll(".app-select.is-open").forEach((wrap) => {
    if (wrap === exceptWrap) return;
    wrap.classList.remove("is-open", "is-up");
    const trigger = wrap.querySelector(".app-select-trigger");
    const menu = wrap._menu;
    if (trigger) trigger.setAttribute("aria-expanded", "false");
    if (menu) menu.hidden = true;
  });
}

function placeAppSelectMenu(wrap) {
  const trigger = wrap.querySelector(".app-select-trigger");
  const menu = wrap._menu;
  if (!trigger || !menu) return;
  const rect = trigger.getBoundingClientRect();
  const minWidth = wrap.classList.contains("is-pill") ? 216 : rect.width;
  const width = Math.max(rect.width, minWidth);
  let left = wrap.classList.contains("is-pill") ? rect.right - width : rect.left;
  left = Math.min(Math.max(12, left), window.innerWidth - width - 12);
  const spaceBelow = window.innerHeight - rect.bottom;
  const openUp = spaceBelow < 220 && rect.top > spaceBelow;
  wrap.classList.toggle("is-up", openUp);
  menu.style.width = `${width}px`;
  menu.style.left = `${left}px`;
  menu.style.right = "auto";
  if (openUp) {
    menu.style.top = "auto";
    menu.style.bottom = `${window.innerHeight - rect.top + 8}px`;
  } else {
    menu.style.top = `${rect.bottom + 8}px`;
    menu.style.bottom = "auto";
  }
}

function enhanceSelect(select) {
  if (select.dataset.enhanced === "1" || select.multiple || select.size > 1) return;
  select.dataset.enhanced = "1";

  const wrap = document.createElement("div");
  wrap.className = "app-select";
  if (select.classList.contains("filter-pill")) wrap.classList.add("is-pill");
  select.parentNode.insertBefore(wrap, select);
  wrap.appendChild(select);

  const trigger = document.createElement("button");
  trigger.type = "button";
  trigger.className = "app-select-trigger";
  trigger.setAttribute("aria-haspopup", "listbox");
  trigger.setAttribute("aria-expanded", "false");
  if (select.id) trigger.setAttribute("aria-labelledby", select.id);
  const aria = select.getAttribute("aria-label");
  if (aria) trigger.setAttribute("aria-label", aria);

  const label = document.createElement("span");
  const chevron = document.createElement("i");
  chevron.className = "bi bi-chevron-down";
  chevron.setAttribute("aria-hidden", "true");
  trigger.append(label, chevron);

  const menu = document.createElement("div");
  menu.className = "app-select-menu";
  menu.setAttribute("role", "listbox");
  menu.hidden = true;
  wrap._menu = menu;
  document.body.appendChild(menu);
  wrap.append(trigger);

  const sync = () => {
    const current = select.options[select.selectedIndex];
    label.textContent = current ? current.text : "";
    menu.replaceChildren();
    [...select.options].forEach((opt, index) => {
      const option = document.createElement("button");
      option.type = "button";
      option.className = "app-select-option";
      option.setAttribute("role", "option");
      option.textContent = opt.text;
      if (opt.disabled) option.disabled = true;
      if (opt.selected) {
        option.classList.add("is-selected");
        option.setAttribute("aria-selected", "true");
      }
      option.addEventListener("click", () => {
        select.selectedIndex = index;
        select.dispatchEvent(new Event("input", { bubbles: true }));
        select.dispatchEvent(new Event("change", { bubbles: true }));
        sync();
        closeAppSelects();
      });
      menu.appendChild(option);
    });
  };

  const open = () => {
    closeAppSelects(wrap);
    wrap.classList.add("is-open");
    trigger.setAttribute("aria-expanded", "true");
    menu.hidden = false;
    placeAppSelectMenu(wrap);
  };

  trigger.addEventListener("click", (event) => {
    event.preventDefault();
    if (select.disabled) return;
    if (wrap.classList.contains("is-open")) closeAppSelects();
    else open();
  });

  select.addEventListener("change", sync);
  sync();
}

function enhanceSelects(root = document) {
  root.querySelectorAll("select").forEach(enhanceSelect);
}

enhanceSelects();
document.addEventListener("htmx:afterSwap", (event) => {
  enhanceSelects(event.target);
});
document.addEventListener("click", (event) => {
  if (!event.target.closest(".app-select") && !event.target.closest(".app-select-menu")) {
    closeAppSelects();
  }
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeAppSelects();
});
window.addEventListener("resize", () => {
  document.querySelectorAll(".app-select.is-open").forEach(placeAppSelectMenu);
});
window.addEventListener(
  "scroll",
  () => {
    document.querySelectorAll(".app-select.is-open").forEach(placeAppSelectMenu);
  },
  true
);

document.body.classList.add("page-ready");

(function initMotion() {
  document.addEventListener("htmx:afterSwap", (event) => {
    const root = event.target;
    if (!(root instanceof Element)) return;
    root.querySelectorAll(".listing-card, .admin-card, .reveal").forEach((el, index) => {
      el.classList.add("htmx-added");
      el.style.setProperty("--d", `${Math.min(index, 8) * 0.04}s`);
    });
  });
})();

(function initBoostFab() {
  const root = document.getElementById("boost-fab");
  if (!root) return;
  const panel = document.getElementById("boost-fab-panel");
  const peek = document.getElementById("boost-fab-peek");
  const collapseBtn = document.getElementById("boost-fab-collapse");
  const hideBtn = document.getElementById("boost-fab-hide");
  const key = "fallaman_boost_fab";

  function readState() {
    try {
      return JSON.parse(localStorage.getItem(key) || "{}");
    } catch (_) {
      return {};
    }
  }

  function writeState(next) {
    localStorage.setItem(key, JSON.stringify(next));
  }

  function apply() {
    const state = readState();
    root.classList.toggle("is-collapsed", !!state.collapsed);
    root.classList.toggle("is-hidden", !!state.hidden);
    root.dataset.collapsed = state.collapsed ? "1" : "0";
    root.dataset.hidden = state.hidden ? "1" : "0";
    if (peek) peek.hidden = !state.hidden;
    if (panel) panel.hidden = !!state.hidden;
  }

  collapseBtn?.addEventListener("click", () => {
    const state = readState();
    state.collapsed = !state.collapsed;
    writeState(state);
    apply();
  });

  hideBtn?.addEventListener("click", () => {
    const state = readState();
    state.hidden = true;
    writeState(state);
    apply();
  });

  peek?.addEventListener("click", () => {
    writeState({ collapsed: false, hidden: false });
    apply();
  });

  // Tap icon when collapsed expands again
  root.querySelector(".boost-fab-icon")?.addEventListener("click", (event) => {
    const state = readState();
    if (state.collapsed && !event.target.closest("a")) {
      event.preventDefault();
      state.collapsed = false;
      writeState(state);
      apply();
    }
  });

  apply();
})();

(function initPwaInstall() {
  const STORAGE_KEY = "fallaman_pwa_install";
  const SESSION_KEY = "fallaman_pwa_popup_shown";
  const DISMISS_MS = 14 * 24 * 60 * 60 * 1000;
  const modal = document.getElementById("pwa-install-modal");
  const soonModal = document.getElementById("app-store-soon-modal");
  const soonText = document.getElementById("app-store-soon-text");
  const soonPwaBtn = document.getElementById("app-store-soon-pwa");
  const iosSteps = document.getElementById("pwa-ios-steps");
  const howtoSteps = document.getElementById("pwa-howto-steps");
  let deferredPrompt = null;

  function isStandalone() {
    return (
      window.matchMedia("(display-mode: standalone)").matches ||
      window.navigator.standalone === true
    );
  }

  function isIos() {
    return /iphone|ipad|ipod/i.test(navigator.userAgent) && !window.MSStream;
  }

  function readState() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
    } catch (_) {
      return {};
    }
  }

  function writeState(next) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  }

  function shouldOffer() {
    if (isStandalone()) return false;
    const state = readState();
    if (state.installed) return false;
    if (state.dismissedAt && Date.now() - state.dismissedAt < DISMISS_MS) return false;
    return true;
  }

  function openModal(el, focusSel) {
    if (!el) return;
    el.hidden = false;
    requestAnimationFrame(() => {
      el.classList.add("is-open");
      document.body.classList.add("pwa-modal-open");
      const focusEl = focusSel ? el.querySelector(focusSel) : null;
      if (focusEl) focusEl.focus();
    });
  }

  function closeModal(el) {
    if (!el) return;
    el.classList.remove("is-open");
    el.hidden = true;
    const otherOpen =
      (modal && modal !== el && modal.classList.contains("is-open")) ||
      (soonModal && soonModal !== el && soonModal.classList.contains("is-open"));
    if (!otherOpen) document.body.classList.remove("pwa-modal-open");
  }

  function showPopup() {
    if (!modal || !shouldOffer()) return;
    openModal(modal, "[data-pwa-install]");
    try {
      sessionStorage.setItem(SESSION_KEY, "1");
    } catch (_) {
      /* ignore */
    }
  }

  function hidePopup() {
    closeModal(modal);
  }

  function hideSoonPopup() {
    closeModal(soonModal);
  }

  function showStoreSoon(platform) {
    if (!soonModal) return;
    hidePopup();
    const label = platform === "ios" ? "iOS (App Store)" : "Android (Play Store)";
    if (soonText) {
      if (isStandalone()) {
        soonText.textContent =
          `L'application ${label} arrive bientôt. Vous utilisez déjà Fallaman installé sur cet appareil.`;
      } else {
        soonText.textContent =
          `L'application ${label} arrive bientôt. En attendant, installez Fallaman sur votre écran d'accueil.`;
      }
    }
    if (soonPwaBtn) {
      soonPwaBtn.hidden = isStandalone();
    }
    openModal(soonModal, isStandalone() ? "[data-app-store-soon-dismiss]" : "[data-app-store-soon-pwa]");
  }

  function openHowto() {
    if (iosSteps) iosSteps.hidden = !isIos();
    if (howtoSteps) howtoSteps.hidden = isIos();
    hidePopup();
    hideSoonPopup();
    if (window.FallamanUI) FallamanUI.openSheet("pwa-install-sheet");
  }

  async function promptInstall() {
    if (deferredPrompt) {
      deferredPrompt.prompt();
      const choice = await deferredPrompt.userChoice;
      deferredPrompt = null;
      if (choice && choice.outcome === "accepted") {
        writeState({ installed: true });
        hidePopup();
        hideSoonPopup();
        return;
      }
    }
    openHowto();
  }

  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    deferredPrompt = event;
    document.body.classList.add("pwa-installable");
  });

  window.addEventListener("appinstalled", () => {
    writeState({ installed: true });
    hidePopup();
    hideSoonPopup();
  });

  document.addEventListener("click", (event) => {
    const storePending = event.target.closest("[data-app-store-pending]");
    if (storePending) {
      event.preventDefault();
      showStoreSoon(storePending.getAttribute("data-app-store-pending") || "android");
      return;
    }
    if (event.target.closest("[data-app-store-soon-dismiss]")) {
      event.preventDefault();
      hideSoonPopup();
      return;
    }
    if (event.target.closest("[data-app-store-soon-pwa]")) {
      event.preventDefault();
      hideSoonPopup();
      promptInstall();
      return;
    }
    if (event.target.closest("[data-pwa-dismiss]")) {
      event.preventDefault();
      writeState({ dismissedAt: Date.now() });
      hidePopup();
      return;
    }
    if (event.target.closest("[data-pwa-install]")) {
      event.preventDefault();
      promptInstall();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    if (soonModal && soonModal.classList.contains("is-open")) {
      hideSoonPopup();
      return;
    }
    if (modal && modal.classList.contains("is-open")) {
      writeState({ dismissedAt: Date.now() });
      hidePopup();
    }
  });

  if (isStandalone()) {
    document.body.classList.add("pwa-standalone");
    return;
  }
  let alreadyShown = false;
  try {
    alreadyShown = sessionStorage.getItem(SESSION_KEY) === "1";
  } catch (_) {
    alreadyShown = false;
  }
  if (shouldOffer() && !alreadyShown) {
    window.setTimeout(showPopup, 500);
  }
})();
