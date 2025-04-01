$(document).ready(function () {
    // Vérifie si originalData a bien été injecté depuis le template
    if (typeof originalData === 'undefined') {
        console.error("Données manquantes : la variable 'originalData' n'est pas définie.");
        return;
    }

    // Fonction pour initialiser DataTables
    function initDataTable() {
        return $('.data-table').DataTable({
            scrollX: true,
            data: transformDataForDataTable(originalData),
            columns: [
                {data: 'username', width: '150px'},
                {data: 'exerciceId', width: '100px'},
                {data: 'exerciceTitre', width: '150px'},
                {data: 'solution', width: '100px'},
                {data: 'expected', width: '100px'}
            ],
            columnDefs: [
                {targets: "_all", className: "dt-head-center"}
            ],
            language: {
                "lengthMenu": "Afficher _MENU_ éléments par page",
                "zeroRecords": "Aucun élément trouvé",
                "info": "Affichage de la page _PAGE_ sur _PAGES_",
                "infoEmpty": "Aucun enregistrement disponible",
                "infoFiltered": "(filtré de _MAX_ enregistrements au total)",
                "search": "Recherche:",
                "paginate": {
                    "first": "Premier",
                    "last": "Dernier",
                    "next": "Suivant",
                    "previous": "Précédent"
                }
            }
        });
    }

    function transformDataForDataTable(data) {
        return data.map(item => ({
            username: `<div class="scrollable-cell" style="width:100px;">${item.username}</div>`,
            exerciceId: `<div class="scrollable-cell" style="width:100px;">${item.exerciceId}</div>`,
            exerciceTitre: `<div class="scrollable-cell" style="width:100px;">${item.exerciceTitre}</div>`,
            solution: `<div class="scrollable-cell" style="width:200px;">${item.solution}</div>`,
            expected: `<div class="scrollable-cell" style="width:200px;">${item.expected}</div>`
        }));
    }

    let table = initDataTable();

    function filterData() {
        const exerciceId = $('#exercice-select').val();
        const participantId = $('#participant-select').val();

        const filteredData = originalData.filter(item => {
            const matchesExercice = exerciceId === "all" || item.exerciceId.toString() === exerciceId;
            const matchesParticipant = participantId === "all" || item.participantId.toString() === participantId;
            return matchesExercice && matchesParticipant;
        });

        table.clear();
        table.rows.add(transformDataForDataTable(filteredData));
        table.draw();
    }

    $('#exercice-select, #participant-select').change(filterData);
    filterData();
});

$(document).ready(function () {
    $('table.participants-table').DataTable({
        language: {
            lengthMenu: "Afficher _MENU_ éléments par page",
            zeroRecords: "Aucun élément trouvé",
            info: "Affichage de la page _PAGE_ sur _PAGES_",
            infoEmpty: "Aucun enregistrement disponible",
            infoFiltered: "(filtré de _MAX_ enregistrements au total)",
            search: "Recherche:",
            paginate: {
                first: "Premier",
                last: "Dernier",
                next: "Suivant",
                previous: "Précédent"
            },
            aria: {
                sortAscending: ": activer pour trier la colonne par ordre croissant",
                sortDescending: ": activer pour trier la colonne par ordre décroissant"
            }
        }
    });
});
