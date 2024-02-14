document.addEventListener('DOMContentLoaded', function () {
    const checkboxAvecJeuDeTest = document.getElementById('id_avec_jeu_de_test');
    const elementsAvecHiddenJDT = document.querySelectorAll('.hiddenjdt');
    const retourEnDirect = document.getElementById('id_retour_en_direct');

    function updateCounts() {
        const jeuxDeTestValue = document.getElementById('id_jeux_de_test').value.split('\n').filter(line => line.trim() !== '').length;
        const resultatsValue = document.getElementById('id_resultats_jeux_de_test').value.split('\n').filter(line => line.trim() !== '').length;
        document.getElementById('nombre_jeux_test').textContent = jeuxDeTestValue;
        document.getElementById('nombre_resultats').textContent = resultatsValue;
    }

    document.getElementById('id_jeux_de_test').addEventListener('input', updateCounts);
    document.getElementById('id_resultats_jeux_de_test').addEventListener('input', updateCounts);

    checkboxAvecJeuDeTest.addEventListener('change', function () {
        // Mettre à jour le champ "retour en direct" pour qu'il soit désactivé et non coché quand "avec jeu de test" change
        retourEnDirect.checked = false;
        retourEnDirect.disabled = !checkboxAvecJeuDeTest.checked;
        elementsAvecHiddenJDT.forEach(function (element) {
            element.classList.toggle('hiddenjdt', !checkboxAvecJeuDeTest.checked);
        });
    });

    // S'assurer que l'état initial des champs est correct, y compris pour "retour en direct"
    if (checkboxAvecJeuDeTest.checked) {
        elementsAvecHiddenJDT.forEach(function (element) {
            element.classList.remove('hiddenjdt');
        });
        retourEnDirect.disabled = false;
    } else {
        retourEnDirect.disabled = true;
    }

    updateCounts(); // S'assure que les compteurs sont à jour dès le chargement

    // Initialisation des tooltips pour Bootstrap 5
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.forEach(function (tooltipTriggerEl) {
        new bootstrap.Tooltip(tooltipTriggerEl);
    });
});