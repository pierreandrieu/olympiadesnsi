document.addEventListener('DOMContentLoaded', function () {
    // Initialisation des tooltips pour Bootstrap 5
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.forEach(function (tooltipTriggerEl) {
        new bootstrap.Tooltip(tooltipTriggerEl);
    });


    // Configuration de la confirmation de suppression pour les modals
    const confirmDeleteModalEl = document.getElementById('confirmDeleteModal');
    const confirmDeleteForm = document.getElementById('confirmDeleteForm'); // Récupère le formulaire par son ID
    confirmDeleteModalEl.addEventListener('show.bs.modal', function (event) {
        let button = event.relatedTarget;
        confirmDeleteForm.action = button.getAttribute('data-epreuve-url'); // Met à jour l'action du formulaire
    });

    const confirmDeleteGroupModal = document.getElementById('confirmDeleteGroupModal');
    confirmDeleteGroupModal.addEventListener('show.bs.modal', function (event) {
        let button = event.relatedTarget;
        this.querySelector('form').action = button.getAttribute('data-groupe-url');
    });

    const addOrganizerModal = document.getElementById('addOrganizerModal');
    addOrganizerModal.addEventListener('show.bs.modal', function (event) {
        let button = event.relatedTarget;
        document.getElementById('addOrganizerForm').action = button.getAttribute('data-ajout-orga-url');
    });

    // Fonction de toggle pour l'affichage des éléments
    window.toggleExercices = function (id) {
        let element = document.getElementById(id);
        element.style.display = element.style.display === "none" ? "table-row" : "none";
    };

    window.toggleComite = function (id) {
        const element = document.getElementById(id);
        const isVisible = element.style.display !== "none";
        document.querySelectorAll('[id^="exercices-"], [id^="comite-"], [id^="groupes-"]').forEach(function (el) {
            el.style.display = "none";
        });
        if (!isVisible) {
            element.style.display = "block";
        }
    };

    window.toggleMembres = function(id) {
        let element = document.getElementById(id);
        element.style.display = element.style.display === "none" ? "table-row" : "none";
    };
});