/**
 * Désactive le bouton de soumission pour un exercice donné.
 * @param {number} exerciceId - L'ID de l'exercice concerné.
 */
export function desactiveBoutonSoumission(exerciceId) {
    let submissionButton = document.getElementById(`btn-submit-participant-${exerciceId}`);
    if (submissionButton) {
        submissionButton.disabled = true;
    }
}

/**
 * Active le bouton de soumission pour un exercice donné.
 * @param {number} exerciceId - L'ID de l'exercice concerné.
 */
export function activeBoutonSoumission(exerciceId) {
    let submissionButton = document.getElementById(`btn-submit-participant-${exerciceId}`);
    if (submissionButton) {
        submissionButton.disabled = false;
    }
}


/* export function creeBoutonSubmit() {
    const submissionButton = document.createElement('button');
    submissionButton.id = 'btn-submit-participant';
    submissionButton.className = 'btn nav-btn';
    submissionButton.innerText = 'Envoyez votre réponse';
    return submissionButton;
}
*/
