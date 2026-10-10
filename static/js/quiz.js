(function () {
  document.addEventListener("DOMContentLoaded", function () {
    var root = document.getElementById("quiz-app");
    var form = document.getElementById("quiz-form");
    if (!root || !form) return;

    var cards = Array.prototype.slice.call(form.querySelectorAll("[data-question-card]"));
    var index = 0;
    var prev = document.getElementById("quiz-prev");
    var next = document.getElementById("quiz-next");
    var submit = document.getElementById("quiz-submit");
    var fill = document.getElementById("quiz-progress-fill");
    var label = document.getElementById("quiz-progress-label");
    var status = document.getElementById("quiz-status");

    function show(i) {
      cards.forEach(function (card, cardIndex) {
        card.hidden = cardIndex !== i;
      });
      prev.disabled = i === 0;
      next.hidden = i === cards.length - 1;
      submit.hidden = i !== cards.length - 1;
      var percent = ((i + 1) / cards.length) * 100;
      fill.style.width = percent + "%";
      label.textContent = "Question " + (i + 1) + " of " + cards.length;
    }

    function selected(card) {
      var checked = card.querySelector("input[type=radio]:checked");
      return checked ? checked.value : null;
    }

    prev.addEventListener("click", function () {
      if (index > 0) {
        index -= 1;
        show(index);
      }
    });

    next.addEventListener("click", function () {
      if (!selected(cards[index])) {
        alert("Choose an answer before continuing.");
        return;
      }
      if (index < cards.length - 1) {
        index += 1;
        show(index);
      }
    });

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      var answers = [];
      for (var i = 0; i < cards.length; i += 1) {
        var value = selected(cards[i]);
        if (!value) {
          index = i;
          show(index);
          alert("Answer every question before submitting.");
          return;
        }
        var input = cards[i].querySelector("input[type=radio]");
        answers.push({
          question_id: Number(input.name.replace("q-", "")),
          selected_option: value,
        });
      }
      if (!window.confirm("Submit this quiz? You can review correct answers afterward.")) {
        return;
      }
      submit.disabled = true;
      status.hidden = false;
      status.className = "status";
      status.textContent = "Scoring your answers…";
      window.edubridge
        .postJson("/api/quiz/submit", {
          track: root.getAttribute("data-track"),
          answers: answers,
        })
        .then(function (data) {
          var attemptId = data.result.attempt_id;
          window.location.href = "/analysis/" + attemptId;
        })
        .catch(function (error) {
          submit.disabled = false;
          status.className = "status error";
          status.textContent = error.message;
        });
    });

    show(0);
  });
})();
