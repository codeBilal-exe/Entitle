(function () {
  "use strict";

  // Tabs: one page, sections switch in place. The URL hash keeps the place on reload.
  var nav = document.querySelector("[data-tabs]");
  if (nav) {
    var links = Array.prototype.slice.call(nav.querySelectorAll("[data-tab]"));
    var panels = Array.prototype.slice.call(document.querySelectorAll("[data-panel]"));
    var names = links.map(function (a) { return a.getAttribute("data-tab"); });
    document.body.classList.add("has-tabs");

    var show = function (name, scroll) {
      if (names.indexOf(name) === -1) name = names[0];
      links.forEach(function (a) {
        var on = a.getAttribute("data-tab") === name;
        a.classList.toggle("is-active", on);
        if (on) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
      });
      panels.forEach(function (p) { p.hidden = p.getAttribute("data-panel") !== name; });
      if (scroll) nav.scrollIntoView({ behavior: "smooth", block: "start" });
    };

    var fromHash = function () {
      var hash = (location.hash || "").slice(1);
      if (hash.indexOf("job-") === 0) {
        show("review", false);
        var target = document.getElementById(hash);
        if (target) setTimeout(function () { target.scrollIntoView({ behavior: "smooth", block: "start" }); }, 60);
        return;
      }
      show(hash, false);
    };

    links.forEach(function (a) {
      a.addEventListener("click", function (event) {
        event.preventDefault();
        var name = a.getAttribute("data-tab");
        history.replaceState(null, "", "#" + name);
        show(name, false);
      });
    });
    document.addEventListener("click", function (event) {
      var link = event.target.closest("[data-tab-link]");
      if (!link) return;
      event.preventDefault();
      var name = link.getAttribute("data-tab-link");
      history.replaceState(null, "", "#" + name);
      show(name, true);
    });
    window.addEventListener("hashchange", fromHash);
    fromHash();
  }

  // Busy state so a slow AI call never looks frozen, and a second click never double-submits.
  document.addEventListener("submit", function (event) {
    var form = event.target;
    var message = form.getAttribute("data-confirm");
    if (message && !window.confirm(message)) {
      event.preventDefault();
      return;
    }
    var button = event.submitter || form.querySelector("button[type=submit]");
    if (button && button.hasAttribute("data-busy")) {
      button.textContent = button.getAttribute("data-busy");
    }
    Array.prototype.forEach.call(form.querySelectorAll("button"), function (b) {
      setTimeout(function () { b.disabled = true; }, 0);
    });
    if (form.hasAttribute("data-run")) startLivePipe(form);
  });

  // While the server runs the real pipeline, light up the steps in order.
  // The page that comes back shows the real result and timings for every step.
  function startLivePipe(form) {
    var url = form.querySelector("input[name=url]");
    var text = form.querySelector("textarea[name=notice_text]");
    if (!(url && url.value.trim()) && !(text && text.value.trim())) return;
    var live = document.querySelector("[data-pipe-live]");
    var still = document.querySelector("[data-pipe-static]");
    if (!live) return;
    if (still) still.hidden = true;
    live.hidden = false;
    live.scrollIntoView({ behavior: "smooth", block: "center" });
    var steps = Array.prototype.slice.call(live.querySelectorAll(".pipe-step"));
    var timing = [0, 1400, 5200, 6400, 7400];
    var words = [
      "Downloading the page",
      "Reading the eligibility text",
      "Checking each quote against the page",
      "Re-checking every profile",
      "Handing it to you"
    ];
    steps.forEach(function (step, i) {
      if (i > 4) return;
      setTimeout(function () {
        steps.forEach(function (s, j) {
          if (j < i) { s.classList.remove("status-running"); s.classList.add("status-ok"); }
        });
        step.classList.remove("status-todo");
        step.classList.add("status-running");
        var detail = step.querySelector(".pipe-detail");
        if (detail) detail.textContent = words[i];
      }, timing[i]);
    });
  }

  // Admin sign-in dialog: the top-bar button, a #admin link, or a failed attempt opens it.
  var dialog = document.getElementById("admin-dialog");
  if (dialog && typeof dialog.showModal === "function") {
    var openAdmin = function () {
      if (dialog.open) return;
      dialog.showModal();
      var first = dialog.querySelector("input[name=username]");
      if (first) first.focus();
    };
    document.addEventListener("click", function (event) {
      if (event.target.closest("[data-open-admin]")) openAdmin();
      if (event.target.closest("[data-close-admin]")) dialog.close();
    });
    dialog.addEventListener("click", function (event) {
      if (event.target === dialog) dialog.close();
    });
    dialog.addEventListener("close", function () {
      if (location.hash === "#admin") history.replaceState(null, "", location.pathname + location.search);
    });
    if (dialog.hasAttribute("data-autoopen") || location.hash === "#admin") openAdmin();
  }

  // Question form: count what is answered so the progress bar moves as you go.
  Array.prototype.forEach.call(document.querySelectorAll("[data-quiz]"), function (form) {
    var count = form.querySelector("[data-quiz-count]");
    var bar = form.querySelector("[data-quiz-bar]");
    var items = form.querySelectorAll(".q");
    var update = function () {
      var done = 0;
      Array.prototype.forEach.call(items, function (item) {
        var field = item.querySelector("[data-q]");
        var picked = item.querySelector("input[type=radio]:checked");
        var answered = field ? field.value.trim() !== "" : !!(picked && picked.value !== "");
        item.classList.toggle("is-answered", answered);
        if (answered) done += 1;
      });
      if (count) count.textContent = done;
      if (bar) bar.style.width = Math.round((done / items.length) * 100) + "%";
    };
    form.addEventListener("input", update);
    form.addEventListener("change", update);
    update();
  });

  // Ask for an email only after someone opts into Entitle updates.
  Array.prototype.forEach.call(document.querySelectorAll("[data-email-optin]"), function (group) {
    var yes = group.querySelector("[data-email-yes]");
    var field = group.querySelector("[data-email-field]");
    var email = group.querySelector("input[name=notification_email]");
    var updateEmailField = function () {
      var enabled = !!(yes && yes.checked);
      if (field) field.hidden = !enabled;
      if (email) email.required = enabled;
    };
    group.addEventListener("change", updateEmailField);
    updateEmailField();
  });

  // Convert redirected server messages into accessible, dismissible toasts.
  Array.prototype.forEach.call(document.querySelectorAll("[data-toast]"), function (toast) {
    var timer;
    var dismissed = false;
    var duration = toast.classList.contains("flash-error") || toast.classList.contains("flash-warn") ? 10000 : 7000;
    var dismiss = function () {
      if (dismissed) return;
      dismissed = true;
      window.clearTimeout(timer);
      toast.classList.add("is-leaving");
      window.setTimeout(function () { toast.remove(); }, 260);
    };
    var schedule = function () {
      window.clearTimeout(timer);
      if (!dismissed) timer = window.setTimeout(dismiss, duration);
    };
    var close = toast.querySelector("[data-toast-dismiss]");
    if (close) close.addEventListener("click", dismiss);
    toast.addEventListener("mouseenter", function () { window.clearTimeout(timer); });
    toast.addEventListener("mouseleave", schedule);
    toast.addEventListener("focusin", function () { window.clearTimeout(timer); });
    toast.addEventListener("focusout", function () {
      window.setTimeout(function () {
        if (!toast.contains(document.activeElement)) schedule();
      }, 0);
    });
    schedule();
  });

  // Load each provider's official favicon first, then try two domain icon services.
  Array.prototype.forEach.call(document.querySelectorAll("[data-provider-logo] img"), function (image) {
    var logo = image.closest("[data-provider-logo]");
    var fallbacks = [image.getAttribute("data-icon-fallback"), image.getAttribute("data-icon-alt")].filter(Boolean);
    var fallbackIndex = 0;
    var showImage = function () { logo.classList.add("has-image"); };
    var tryFallback = function () {
      if (fallbackIndex < fallbacks.length) {
        image.src = fallbacks[fallbackIndex++];
        return;
      }
      logo.classList.add("icon-missing");
    };
    image.addEventListener("load", showImage);
    image.addEventListener("error", tryFallback);
    if (image.complete) {
      if (image.naturalWidth > 0) showImage();
      else tryFallback();
    }
  });

  // Play the transparent Entitle logo when it enters view, with reduced-motion support.
  Array.prototype.forEach.call(document.querySelectorAll(".elx"), function (logo) {
    var timer;
    var started = false;
    var reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    Array.prototype.forEach.call(logo.querySelectorAll(".elx-word span"), function (letter, index) {
      letter.style.setProperty("--elx-i", index);
    });
    if (reduced) return;

    var play = function () {
      logo.classList.remove("is-playing");
      void logo.offsetWidth;
      logo.classList.add("is-playing");
    };
    var loop = function () {
      var interval = parseInt(logo.getAttribute("data-loop"), 10);
      if (!interval) return;
      window.clearTimeout(timer);
      timer = window.setTimeout(function () { play(); loop(); }, interval);
    };
    var start = function () {
      if (started) return;
      started = true;
      play();
      loop();
    };

    if ("IntersectionObserver" in window) {
      var observer = new IntersectionObserver(function (entries) {
        if (!entries[0].isIntersecting) return;
        start();
        observer.disconnect();
      }, { threshold:.3 });
      observer.observe(logo);
    } else start();

    logo.addEventListener("click", function () { play(); loop(); });
    logo.addEventListener("keydown", function (event) {
      if (event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault();
      play();
      loop();
    });

    if (window.matchMedia && window.matchMedia("(hover:hover)").matches) {
      var mark = logo.querySelector(".elx-mark");
      logo.addEventListener("pointermove", function (event) {
        var bounds = mark.getBoundingClientRect();
        var x = (event.clientX - (bounds.left + bounds.width / 2)) / window.innerWidth * 2;
        var y = (event.clientY - (bounds.top + bounds.height / 2)) / window.innerHeight * 2;
        x = Math.max(-1, Math.min(1, x));
        y = Math.max(-1, Math.min(1, y));
        logo.style.setProperty("--elx-rx", (x * 18).toFixed(2));
        logo.style.setProperty("--elx-ry", (y * 18).toFixed(2));
        logo.style.setProperty("--elx-sx", (50 + x * 40) + "%");
        logo.style.setProperty("--elx-sy", (35 + y * 40) + "%");
      }, { passive:true });
    }
  });

  // Bring a freshly run job into view.
  if (location.search.indexOf("job=") !== -1 && location.hash.indexOf("#job-") === 0) {
    var el = document.querySelector(location.hash);
    if (el) el.classList.add("is-fresh");
  }

  // Reveal page sections and cards as they enter view. Without IntersectionObserver
  // or with reduced motion enabled, content stays visible and in normal document flow.
  var reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var revealItems = Array.prototype.slice.call(document.querySelectorAll(
    "main > section, main > nav, .prog, .packet, .alert, .job, .held, .rule, .receipt, .pipe-step, .run, .stats, .table, .log, .empty"
  ));
  if (!reduceMotion && "IntersectionObserver" in window && revealItems.length) {
    revealItems.forEach(function (item, index) {
      item.setAttribute("data-reveal", item.matches(".prog, .packet, .alert, .job, .held, .rule, .receipt, .pipe-step") ? "item" : "section");
      if (item.getAttribute("data-reveal") === "item") {
        item.style.setProperty("--reveal-delay", Math.min(index % 4, 3) * 65 + "ms");
      }
    });
    document.body.classList.add("reveal-ready");
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("is-visible");
        observer.unobserve(entry.target);
      });
    }, { threshold: 0.16, rootMargin: "0px 0px -7% 0px" });
    revealItems.forEach(function (item) {
      if (item.matches(".hero")) item.setAttribute("data-reveal", "section");
      observer.observe(item);
    });
  }

  // The 3D timeline follows the page scroll through its four steps.
  var timeline = document.querySelector("[data-hero-scroll]");
  if (timeline) {
    var items = Array.prototype.slice.call(timeline.querySelectorAll(".tl-item"));
    var scenes = Array.prototype.slice.call(timeline.querySelectorAll(".tl-s"));
    var fill = timeline.querySelector(".tl-fill");
    var scene = timeline.querySelector(".tl-scene");
    var count = timeline.querySelector(".tl-count b");
    var clamp = function (value, min, max) { return Math.max(min, Math.min(max, value)); };
    var positions = [];
    var measure = function () { positions = items.map(function (item) { return item.offsetTop + 13; }); };
    var frame = function () {
      if (!items.length || !scenes.length || !fill) return;
      var bounds = timeline.getBoundingClientRect();
      var span = bounds.height - window.innerHeight;
      var progress = span > 0 ? clamp(-bounds.top / span, 0, 1) : 1;
      var step = progress * items.length;
      scenes.forEach(function (el, index) {
        var local = step - index;
        var opacity = 1;
        var transform = "none";
        if (local < 0) {
          var entering = clamp(1 + local / .35, 0, 1);
          opacity = entering;
          transform = "translate3d(" + ((1 - entering) * 140) + "px,0," + ((entering - 1) * 420) + "px) rotateY(" + ((1 - entering) * 55) + "deg)";
        } else if (local > 1 && index < scenes.length - 1) {
          var leaving = clamp((local - 1) / .35, 0, 1);
          opacity = 1 - leaving;
          transform = "translate3d(" + (leaving * -140) + "px,0," + (-leaving * 420) + "px) rotateY(" + (leaving * -55) + "deg)";
        }
        el.style.opacity = opacity;
        el.style.transform = transform;
        el.style.setProperty("--g", clamp(local / .88, 0, 1).toFixed(4));
      });
      if (count) count.textContent = clamp(Math.floor(clamp((step - 1) / .88, 0, 1) * 9), 0, 6);
      var active = clamp(Math.floor(step + .25), 0, items.length - 1);
      items.forEach(function (item, index) {
        item.classList.toggle("is-now", index === active);
        item.classList.toggle("is-done", index < active);
        item.classList.toggle("is-on", index <= active);
        if (index === active) item.setAttribute("aria-current", "step");
        else item.removeAttribute("aria-current");
      });
      if (positions.length > 1) {
        var point = clamp(step - .5, 0, items.length - 1);
        var segment = Math.min(Math.floor(point), items.length - 2);
        fill.style.height = (positions[segment] + (positions[segment + 1] - positions[segment]) * (point - segment)) + "px";
      }
    };
    var queued = false;
    var queueFrame = function () {
      if (queued) return;
      queued = true;
      window.requestAnimationFrame(function () { frame(); queued = false; });
    };
    if (!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches)) {
      window.addEventListener("scroll", queueFrame, { passive: true });
      window.addEventListener("resize", function () { measure(); queueFrame(); });
      if (window.matchMedia && window.matchMedia("(hover:hover)").matches && scene) {
        window.addEventListener("pointermove", function (event) {
          scene.style.setProperty("--mx", (event.clientX / window.innerWidth * 2 - 1).toFixed(3));
          scene.style.setProperty("--my", (event.clientY / window.innerHeight * 2 - 1).toFixed(3));
        }, { passive: true });
      }
      if (document.fonts && document.fonts.ready) document.fonts.ready.then(function () { measure(); queueFrame(); });
    }
    if (!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches)) {
      measure();
      frame();
    }
  }
})();
