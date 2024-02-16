document.addEventListener('DOMContentLoaded', function () {
    const inscriptionsExternesCheckbox = document.querySelector('#id_inscription_externe');
    const domainesAutorisesContainer = document.getElementById("domaines-autorises-container");

    function toggleDomainesAutorises() {
        if (inscriptionsExternesCheckbox.checked) {
            domainesAutorisesContainer.classList.remove('hidden-inscription-externe'); // Assurez-vous que c'est bien 'hidden-element' qui est utilisé pour cacher les éléments.
        } else {
            domainesAutorisesContainer.classList.add('hidden-inscription-externe');
        }
        updateDomainesCount(); // Mettre à jour le comptage à chaque toggle
    }

    inscriptionsExternesCheckbox.addEventListener('change', toggleDomainesAutorises);
    toggleDomainesAutorises(); // Appel initial pour définir l'état correct au chargement de la page

    function updateDomainesCount() {
        const textarea = document.querySelector('#id_domaines_autorises');
        const countP = document.querySelector('#domaines_count');
        if (textarea) {
            const lines = textarea.value.split('\n').filter(line => line.trim() !== '');
            const domainRegex = /^@\w+([-.\w]+)*\.\w{2,}$/;
            const validDomains = lines.filter(line => domainRegex.test(line));
            const invalidDomains = lines.filter(line => !domainRegex.test(line));
            countP.textContent = `${validDomains.length} domaine(s) valide(s) trouvé(s), ${invalidDomains.length} invalide(s).`;
        }
    }

    const domainesAutorisesInput = document.querySelector('#id_domaines_autorises');
    if (domainesAutorisesInput) {
        domainesAutorisesInput.addEventListener('input', updateDomainesCount);
    }
});