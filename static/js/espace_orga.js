// Initialisation de la DataTable pour le tableau des groupes
$(document).ready(function () {
    $('#tableGroupes').DataTable({
        "language": {
            "lengthMenu": "Afficher _MENU_ éléments par page",
            "zeroRecords": "Aucun élément trouvé",
            "info": "Affichage de la page _PAGE_ sur _PAGES_",
            "infoEmpty": "Aucun enregistrement disponible",
            "infoFiltered": "(filtré de _MAX_ enregistrements au total)",
            "search": "Recherche :",
            "paginate": {
                "first": "Premier",
                "last": "Dernier",
                "next": "Suivant",
                "previous": "Précédent"
            },
            "aria": {
                "sortAscending": ": activer pour trier la colonne par ordre croissant",
                "sortDescending": ": activer pour trier la colonne par ordre décroissant"
            }
        }
    });
});

/**
 * Affiche ou masque dynamiquement une ligne du tableau (tr),
 * utilisée pour les blocs de type : comite, groupes, exercices.
 *
 * @param {string} id - L'identifiant de l'élément <tr> à afficher ou masquer.
 */
function toggleComite(id) {
    const element = document.getElementById(id);
    if (element) {
        const isVisible = element.style.display !== "none";
        element.style.display = isVisible ? "none" : "table-row"; // car ce sont des <tr>
    }
}

/**
 * Affiche ou masque dynamiquement une ligne de tableau contenant les membres d'un groupe.
 *
 * @param {string} id - L'identifiant de l'élément <tr> à afficher ou masquer.
 */
function toggleMembres(id) {
    const element = document.getElementById(id);
    if (element) {
        const isVisible = element.style.display !== "none";
        element.style.display = isVisible ? "none" : "table-row";
    }
}

// Gestion dynamique du formulaire d'ajout d'organisateur (depuis la modale)
document.addEventListener("DOMContentLoaded", function () {
    const modal = document.getElementById("addOrganizerModal");
    const form = document.getElementById("addOrganizerForm");

    if (!modal || !form) return;

    modal.addEventListener("show.bs.modal", function (event) {
        const button = event.relatedTarget;
        const ajoutOrgaUrl = button.getAttribute("data-ajout-orga-url");
        if (ajoutOrgaUrl) {
            form.setAttribute("action", ajoutOrgaUrl);
        }
    });
});
