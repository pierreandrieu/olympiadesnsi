document.addEventListener('DOMContentLoaded', function () {
    const checkboxAvecJeuDeTest = document.getElementById('id_avec_jeu_de_test');
    const elementsAvecHiddenJDT = document.querySelectorAll('.hiddenjdt');
    const retourEnDirect = document.getElementById('id_retour_en_direct');
    const separateurJeuxDeTestInput = document.getElementById('separateur_jeux_de_test');
    const separateurResultatsInput = document.getElementById('separateur_resultats');

    function escapeRegExp(string) {
        return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    function updateCounts() {
        let separateurJeuxDeTest = separateurJeuxDeTestInput.value || '\n'; // Utilise \n comme valeur par défaut
        let separateurResultats = separateurResultatsInput.value || '\n'; // Utilise \n comme valeur par défaut
        separateurJeuxDeTest = escapeRegExp(separateurJeuxDeTest.replace(/\\n/g, '\n'));
        separateurResultats = escapeRegExp(separateurResultats.replace(/\\n/g, '\n'));

        const regexSeparateurJeux = new RegExp(separateurJeuxDeTest.replace(/\\n/g, '\n'), 'g');
        const regexSeparateurResultats = new RegExp(separateurResultats.replace(/\\n/g, '\n'), 'g');

        const jeuxDeTestValue = document.getElementById('id_jeux_de_test').value.split(regexSeparateurJeux).filter(line => line.trim() !== '').length;
        const resultatsValue = document.getElementById('id_resultats_jeux_de_test').value.split(regexSeparateurResultats).filter(line => line.trim() !== '').length;

        document.getElementById('nombre_jeux_test').textContent = jeuxDeTestValue;
        document.getElementById('nombre_resultats').textContent = resultatsValue;
    }

    document.getElementById('id_jeux_de_test').addEventListener('input', updateCounts);
    document.getElementById('id_resultats_jeux_de_test').addEventListener('input', updateCounts);
    // Ajoute des écouteurs d'événements sur les champs de séparateurs pour mettre à jour les décomptes dynamiquement
    separateurJeuxDeTestInput.addEventListener('input', updateCounts);
    separateurResultatsInput.addEventListener('input', updateCounts);

    checkboxAvecJeuDeTest.addEventListener('change', function () {
        retourEnDirect.checked = false;
        retourEnDirect.disabled = !checkboxAvecJeuDeTest.checked;
        elementsAvecHiddenJDT.forEach(function (element) {
            element.classList.toggle('hiddenjdt', !checkboxAvecJeuDeTest.checked);
        });
    });

    if (checkboxAvecJeuDeTest.checked) {
        elementsAvecHiddenJDT.forEach(function (element) {
            element.classList.remove('hiddenjdt');
        });
        retourEnDirect.disabled = false;
    } else {
        retourEnDirect.disabled = true;
    }

    updateCounts(); // Initialiser les compteurs au chargement de la page

    // Initialisation des tooltips Bootstrap 5
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.forEach(function (tooltipTriggerEl) {
        new bootstrap.Tooltip(tooltipTriggerEl);
    });
});
