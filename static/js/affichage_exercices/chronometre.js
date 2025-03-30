/**
 * Initialise le chronomètre pour l'élève en utilisant localStorage.
 * Permet de conserver le compte à rebours même si l'élève recharge la page.
 *
 * @param {string} tempsRestantDataId - L'ID de l'élément script contenant le temps restant en JSON.
 */
function initialiserChronometre(tempsRestantDataId) {
    // Récupère l'élément <script> contenant les données JSON sur le temps restant
    let elem = document.querySelector('script[type="application/json"]#' + tempsRestantDataId);

    // Vérifie que l'élément existe bien pour éviter les erreurs
    if (!elem) return;

    // Convertit le contenu JSON en un nombre (le temps restant en secondes)
    let tempsRestant = JSON.parse(elem.textContent);

    // Vérifie si une heure de fin est déjà stockée dans localStorage
    let heureFinStockee = localStorage.getItem('heureFinChrono');

    if (!heureFinStockee) {
        // Si aucune heure de fin n'est stockée, on la calcule et on l'enregistre.
        let heureFin = Date.now() + tempsRestant * 1000; // Date actuelle + temps restant en millisecondes
        localStorage.setItem('heureFinChrono', heureFin);
    } else {
        // Si une heure de fin est déjà enregistrée, recalculer le temps restant
        let maintenant = Date.now();
        tempsRestant = Math.max(0, Math.floor((heureFinStockee - maintenant) / 1000));
    }

    // Affiche le temps restant au démarrage
    afficherTempsRestant(tempsRestant);

    // Démarre un intervalle qui met à jour le chronomètre chaque seconde
    const intervalId = setInterval(function () {
        if (tempsRestant <= 0) {
            // Si le temps est écoulé, on arrête le chronomètre
            clearInterval(intervalId);
            localStorage.removeItem('heureFinChrono'); // Supprime l'heure de fin enregistrée
            document.getElementById('temps-restant').textContent = '00:00:00'; // Affiche "00:00:00"
        } else {
            // Sinon, on décrémente le temps restant et on l'affiche
            tempsRestant--;
            afficherTempsRestant(tempsRestant);
        }
    }, 1000); // Exécution toutes les 1000ms (1 seconde)
}

/**
 * Met à jour l'affichage du temps restant en format HH:MM:SS.
 *
 * @param {number} tempsRestant - Temps restant en secondes.
 */
function afficherTempsRestant(tempsRestant) {
    const heures = Math.floor(tempsRestant / 3600);
    const minutes = Math.floor((tempsRestant % 3600) / 60);
    const secondes = tempsRestant % 60;

    const elem = document.getElementById('temps-restant');
    if (!elem) return;  // <-- ✅ protection !

    elem.textContent =
        heures.toString().padStart(2, '0') + ':' +
        minutes.toString().padStart(2, '0') + ':' +
        secondes.toString().padStart(2, '0');
}


// Vérifie si l'élément script contenant le temps restant est présent dans la page
if (document.querySelector('script[type="application/json"]#temps-restant-data')) {
    initialiserChronometre('temps-restant-data'); // Démarre le chronomètre
}

/**
 * Nettoie localStorage à la fin de l'épreuve pour éviter que la valeur reste stockée inutilement.
 * Cette fonction est exécutée lorsque l'utilisateur quitte la page.
 */
window.addEventListener("beforeunload", function () {
    const elem = document.getElementById('temps-restant');
    if (elem && elem.textContent === "00:00:00") {
        localStorage.removeItem('heureFinChrono');
    }
});

