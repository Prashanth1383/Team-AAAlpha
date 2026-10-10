(function () {
  document.addEventListener("DOMContentLoaded", function () {
    var node = document.getElementById("dashboard-data");
    var canvas = document.getElementById("scoreChart");
    if (!node || !canvas) return;
    if (typeof window.Chart === "undefined") {
      var note = document.createElement("p");
      note.className = "muted";
      note.textContent = "Chart.js did not load, so the score chart is unavailable in this browser session.";
      canvas.replaceWith(note);
      return;
    }
    var history = JSON.parse(node.textContent || "[]");
    if (!history.length) return;
    new window.Chart(canvas, {
      type: "line",
      data: {
        labels: history.map(function (item, index) {
          return "Attempt " + (index + 1);
        }),
        datasets: [
          {
            label: "Quiz score (%)",
            data: history.map(function (item) {
              return item.score_percent;
            }),
            borderColor: "#2563eb",
            backgroundColor: "rgba(37, 99, 235, 0.12)",
            tension: 0.25,
            fill: true,
          },
        ],
      },
      options: {
        responsive: true,
        plugins: {
          legend: { display: true },
        },
        scales: {
          y: { suggestedMin: 0, suggestedMax: 100 },
        },
      },
    });
  });
})();
