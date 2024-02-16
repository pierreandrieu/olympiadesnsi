document.addEventListener('DOMContentLoaded', function () {
    const exerciceRows = document.querySelectorAll('.exercice-row');

    exerciceRows.forEach(row => {
        row.querySelector('.move-up').addEventListener('click', function () {
            let previous = row.previousElementSibling;
            if (previous) {
                row.parentNode.insertBefore(row, previous);
                updateButtonStates();
            }
        });

        row.querySelector('.move-down').addEventListener('click', function () {
            let next = row.nextElementSibling;
            if (next) {
                // Insérer l'élément actuel après l'élément suivant
                row.parentNode.insertBefore(row, next.nextSibling);
                updateButtonStates();
            }
        });
    });

    function updateButtonStates() {
        // Mettre à jour la liste des exerciceRows à chaque appel
        const exerciceRows = document.querySelectorAll('.exercice-row');
        exerciceRows.forEach((row, index) => {
            let isFirst = index === 0;
            let isLast = index === exerciceRows.length - 1;

            row.querySelector('.move-up').disabled = isFirst;
            row.querySelector('.move-down').disabled = isLast;
        });
        updateOrder()
    }

    updateButtonStates(); // Initialisation des états des boutons
});

function updateOrder() {
    document.querySelectorAll('.exercice-row').forEach((row, index) => {
        row.querySelector('input[type="hidden"]').value = row.getAttribute('data-exercice-id');
    });
}


document.querySelector('form').addEventListener('submit', updateOrder);

