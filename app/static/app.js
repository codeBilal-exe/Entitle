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

  // Bring a freshly run job into view.
  if (location.search.indexOf("job=") !== -1 && location.hash.indexOf("#job-") === 0) {
    var el = document.querySelector(location.hash);
    if (el) el.classList.add("is-fresh");
  }
})();
