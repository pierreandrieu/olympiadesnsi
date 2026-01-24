$(document).ready(function () {
    let $identifiantInput = $('#id_identifiant');
    let $errorMessage = $('#error-message');

    $errorMessage.hide();

    $identifiantInput.on('input', function () {
        let val = $(this).val() || '';
        if (val.includes('@')) {
            $errorMessage
                .text("⚠️ Veuillez ne saisir que votre identifiant académique (avant le @), puis choisir le domaine dans la liste.")
                .show();
        } else {
            $errorMessage.hide();
        }
    });
});

    (function () {
    const btn = document.getElementById("btn-valider-uai");
    const bloc = document.getElementById("bloc-details");
    const msg = document.getElementById("message-uai");

    const inputUai = document.getElementById("id_code_uai");
    const inputNom = document.getElementById("id_nom_etablissement");
    const inputCommune = document.getElementById("id_commune");
    const inputEmail = document.getElementById("id_email_etablissement");

    function setMessage(html, cls) {
    msg.innerHTML = '<div class="alert ' + cls + '">' + html + '</div>';
}

    async function chargerInfos() {
    const code = (inputUai.value || "").trim().toUpperCase();
    inputUai.value = code;

    if (!code) {
    setMessage("Veuillez renseigner un code UAI.", "alert-warning");
    return;
}

    setMessage("Vérification de l’UAI…", "alert-info");

    const url = "{% url 'olympiades_infos_etablissement' %}" + "?code_uai=" + encodeURIComponent(code);
    const resp = await fetch(url, {headers: {"X-Requested-With": "XMLHttpRequest"}});
    const data = await resp.json();

    if (!data.ok) {
    setMessage("Erreur : " + (data.error || "inconnue"), "alert-danger");
    return;
}

    bloc.style.display = "block";

    if (!data.existe) {
    inputNom.value = "";
    inputCommune.value = "";
    inputEmail.value = "";
    setMessage("UAI inconnu : merci de compléter les informations de l’établissement.", "alert-warning");
    return;
}

    inputNom.value = data.etablissement.nom_etablissement || "";
    inputCommune.value = data.etablissement.commune || "";
    inputEmail.value = data.etablissement.email_etablissement || "";
    setMessage("UAI reconnu : informations préremplies (modifiables).", "alert-success");
}

    btn.addEventListener("click", chargerInfos);

    // Petit bonus si l’utilisateur appuie sur Entrée dans le champ UAI
    inputUai.addEventListener("keydown", function (e) {
    if (e.key === "Enter") {
    e.preventDefault();
    chargerInfos();
}
});
})();
