$(document).ready(function () {
    let identifiantInput = $('#id_identifiant');

    identifiantInput.on('input', function () {
        let val = $(this).val();
        if (val.includes('@')) {
            $errorMessage.text("⚠️ Veuillez ne saisir que votre identifiant académique, puis saisir le domaine dans la liste déroulant.").show();
        } else {
            $errorMessage.hide();
        }
    });
    // Sélecteurs
    let $epreuveSelect = $('#id_epreuve');
    let $domaineSelect = $('#id_domaine_academique');
    let $errorMessage = $('#error-message');

    // Cache le message d'erreur au départ
    $errorMessage.hide();

    function updateDomaines() {
        let selectedOption = $epreuveSelect.find('option:selected');
        let epreuveId = selectedOption.val();  // valeur brute, ID (pour POST)
        let hashid = selectedOption.data('hashid');  // utilisé pour AJAX

        if (hashid) {
            $('#id_epreuve_id').val(epreuveId);  // pour que le POST récupère l'ID
            $.ajax({
                url: `/inscription/get_domaines/${hashid}/`,
                type: "GET",
                dataType: "json",
                success: function (data) {
                    $domaineSelect.empty().append($('<option>', {
                        value: '',
                        text: 'Sélectionnez un domaine'
                    }));
                    $.each(data, function (i, domaine) {
                        $domaineSelect.append($('<option>', {
                            value: domaine,
                            text: domaine.substring(1)  // ⚠️ enlevant le premier caractère ?
                        }));
                    });
                },
                error: function (xhr) {
                    console.error("Erreur AJAX :", xhr);
                    $domaineSelect.empty().append($('<option>', {
                        value: '',
                        text: 'Erreur lors du chargement'
                    }));
                }
            });
        } else {
            $domaineSelect.empty().append($('<option>', {
                value: '',
                text: 'Sélectionnez un domaine'
            }));
        }
    }

    // Met à jour les domaines à chaque changement de l'épreuve
    $epreuveSelect.change(function () {
        updateDomaines();
    });

    // Cache le message d'erreur quand le domaine change
    $domaineSelect.change(function () {
        $errorMessage.hide();
    });

    // Mise à jour initiale au chargement
    updateDomaines();
});