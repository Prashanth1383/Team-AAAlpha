(function () {
  function csrfToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute("content") : "";
  }

  window.edubridge = {
    csrfToken: csrfToken,
    postJson: function (url, body) {
      return fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
          "X-CSRFToken": csrfToken(),
        },
        body: JSON.stringify(body || {}),
      }).then(function (response) {
        return response.text().then(function (text) {
          var data = {};
          try {
            data = text ? JSON.parse(text) : {};
          } catch (err) {
            throw new Error("The server returned an unexpected response.");
          }
          if (!response.ok || !data.ok) {
            var error = new Error(data.error || "Request failed.");
            error.status = response.status;
            throw error;
          }
          return data;
        });
      });
    },
  };

  document.addEventListener("DOMContentLoaded", function () {
    if (window.lucide && typeof window.lucide.createIcons === "function") {
      window.lucide.createIcons();
    }

    var toggle = document.querySelector("[data-nav-toggle]");
    var nav = document.getElementById("site-nav");
    if (toggle && nav) {
      toggle.addEventListener("click", function () {
        var open = nav.classList.toggle("open");
        toggle.setAttribute("aria-expanded", open ? "true" : "false");
      });
    }

    document.querySelectorAll("form[data-validate]").forEach(function (form) {
      form.addEventListener("submit", function (event) {
        var track = form.querySelector('[name="track"]');
        var minutes = form.querySelector('[name="daily_minutes"]');
        var days = form.querySelector('[name="target_days"]');
        var level = form.querySelector('[name="experience_level"]:checked');
        var messages = [];
        if (track && !track.value) messages.push("Select a learning track.");
        if (!level) messages.push("Select an experience level.");
        if (minutes) {
          var m = Number(minutes.value);
          if (!m || m < 15 || m > 240) messages.push("Daily minutes must be between 15 and 240.");
        }
        if (days) {
          var d = Number(days.value);
          if (!d || d < 7 || d > 90) messages.push("Target days must be between 7 and 90.");
        }
        var name = form.querySelector('[name="display_name"]');
        if (name && !name.value.trim()) messages.push("Display name is required.");
        if (messages.length) {
          event.preventDefault();
          alert(messages.join("\n"));
        }
      });
    });

    document.querySelectorAll("[data-task-toggle]").forEach(function (box) {
      box.addEventListener("change", function () {
        window.edubridge
          .postJson("/api/tasks/" + box.value + "/complete", { completed: box.checked })
          .then(function () {
            window.location.reload();
          })
          .catch(function (error) {
            box.checked = !box.checked;
            alert(error.message);
          });
      });
    });

    var generate = document.getElementById("generate-plan");
    if (generate) {
      generate.addEventListener("click", function () {
        var status = document.getElementById("plan-status");
        generate.disabled = true;
        if (status) {
          status.hidden = false;
          status.textContent = "Generating plan from your latest quiz results…";
          status.className = "status";
        }
        window.edubridge
          .postJson("/api/study-plan/generate", {})
          .then(function () {
            window.location.reload();
          })
          .catch(function (error) {
            generate.disabled = false;
            if (status) {
              status.textContent = error.message;
              status.className = "status error";
            }
          });
      });
    }
  });
})();
