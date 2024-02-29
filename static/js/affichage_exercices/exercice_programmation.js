import {renderLatex} from './render_latex.js';
import {desactiveBoutonSoumission, activeBoutonSoumission}  from "./bouton_submit.js";
import {getCookie} from "./cookies.js";
import {mettreAJourIndicateur} from "./indicateur_etat.js";

/**
 * Crée et affiche les éléments d'un exercice de programmation dans un conteneur spécifié.
 * @param {Object} exercice - L'objet contenant les informations de l'exercice.
 * @param {HTMLElement} container - L'élément conteneur où afficher l'exercice.
 */
export function creerElementsExercice(exercice, container) {
    // Vide le conteneur pour s'assurer qu'il n'y a pas d'éléments précédents
    container.innerHTML = '';

    // Crée et ajoute le titre de l'exercice
    const titleElement = document.createElement('h2');
    titleElement.textContent = exercice.titre; // Utilise textContent pour éviter les risques XSS
    container.appendChild(titleElement);

// Crée et ajoute l'énoncé de l'exercice, avec gestion du LaTeX
    if (exercice.enonce && exercice.enonce.trim().length > 0) {
        const enonceElement = document.createElement('div');
        renderLatex(exercice.enonce, enonceElement);
        container.appendChild(enonceElement);
    }

    // Vérifie et ajoute l'énoncé de code si présent
    if (exercice.enonce_code && exercice.enonce_code.trim().length > 0) {
        const codeElement = document.createElement('pre');
        const codeContent = document.createElement('code');
        codeContent.textContent = exercice.enonce_code;
        codeElement.appendChild(codeContent);
        container.appendChild(codeElement);
    }

    // Ajoute un champ de réponse et l'instance du jeu de test si l'exercice comporte un jeu de test
    if (exercice.avec_jeu_de_test) {
        // Création du conteneur pour l'instance du jeu de test
        const jeuDeTestContainer = document.createElement('div');
        jeuDeTestContainer.className = 'jeu-de-test-container';

        // Ajout d'un texte explicatif pour l'instance du jeu de test
        const jeuDeTestExplication = document.createElement('p');
        jeuDeTestExplication.textContent = 'Votre jeu de test :';
        jeuDeTestContainer.appendChild(jeuDeTestExplication);

        // Affichage de l'instance du jeu de test
        const jeuDeTestInstance = document.createElement('pre');
        jeuDeTestInstance.className = 'jeu-de-test-instance';
        jeuDeTestInstance.textContent = exercice.instance_de_test;
        jeuDeTestContainer.appendChild(jeuDeTestInstance);

        // Ajout du conteneur du jeu de test au conteneur principal
        container.appendChild(jeuDeTestContainer);

        // Création du conteneur pour la réponse
        const responseContainer = document.createElement('div');
        responseContainer.className = 'instance-response-container';

        // Ajout d'un texte explicatif pour la réponse
        const reponseExplication = document.createElement('p');
        reponseExplication.textContent = 'La solution du jeu de test :';
        responseContainer.appendChild(reponseExplication);

        // Création de l'input pour la réponse
        const inputReponse = document.createElement('input');
        inputReponse.type = 'text';
        inputReponse.id = `instance-response-${exercice.id}`;
        inputReponse.placeholder = 'Votre réponse ici';
        // Initialise avec la réponse précédente si disponible
        inputReponse.value = exercice.reponse_jeu_de_test_enregistree || '';
        responseContainer.appendChild(inputReponse);

        // Ajout du conteneur de réponse au conteneur principal
        container.appendChild(responseContainer);
    }

// Création du champ pour la soumission du code, si nécessaire
    if (exercice.code_a_soumettre) {
        const codeContainer = document.createElement('div');
        codeContainer.className = 'code-submission-container';

        // Ajout d'un texte explicatif pour l'insertion du code
        const codeExplication = document.createElement('p');
        codeExplication.textContent = 'Insérez votre code ici :';
        codeContainer.appendChild(codeExplication);

        // Création et configuration de la zone de texte pour la soumission du code
        const textareaCode = document.createElement('textarea');
        textareaCode.id = `code-submission-${exercice.id}`;
        textareaCode.placeholder = 'Votre code ici';
        // Initialise avec le code précédent si disponible
        textareaCode.textContent = exercice.code_enregistre || '';
        codeContainer.appendChild(textareaCode);

        // Ajout du conteneur de soumission de code au conteneur principal
        container.appendChild(codeContainer);
    }


    // Affiche le nombre de soumissions encore possibles
    const soumissionsInfo = document.createElement('div');
    soumissionsInfo.className = 'soumissions-info';
    soumissionsInfo.id = `soumissions-info-${exercice.id}`;
    const soumissionsRestantes = exercice.nb_soumissions_restantes;
    soumissionsInfo.textContent = `Soumissions restantes : ${soumissionsRestantes}`;
    container.appendChild(soumissionsInfo);

    // Ajoute un bouton de soumission si des soumissions sont encore possibles
    if (exercice.nb_soumissions_restantes > 0) {
        const submissionButton = document.createElement('button');
        submissionButton.id = `btn-submit-participant-${exercice.id}`;
        submissionButton.className = 'btn nav-btn';
        submissionButton.textContent = 'Envoyez votre réponse';
        submissionButton.addEventListener('click', function () {
            soumettreReponse(exercice);
        });
        container.appendChild(submissionButton);
    }
}


/**
 * Met à jour les valeurs dynamiques pour un exercice donné.
 * Cette fonction est appelée pour rafraîchir l'interface utilisateur avec les dernières données,
 * par exemple, après une soumission réussie.
 * @param {Object} exercice - L'objet contenant les informations de l'exercice.
 */
export function mettreAJourValeursExercice(exercice) {
    // Mise à jour de la réponse enregistrée pour le jeu de test, si présent
    if (exercice.avec_jeu_de_test) {
        const inputReponse = document.getElementById(`instance-response-${exercice.id}`);
        if (inputReponse) {
            // Utilisez la valeur enregistrée ou une chaîne vide si aucune réponse n'est enregistrée
            inputReponse.value = exercice.reponse_jeu_de_test_enregistree || '';
        }
    }

    // Mise à jour du code soumis par l'utilisateur, si applicable
    if (exercice.code_a_soumettre) {
        const textareaCode = document.getElementById(`code-submission-${exercice.id}`);
        if (textareaCode) {
            // Utilisez le code enregistré ou une chaîne vide si aucun code n'est enregistré
            textareaCode.value = exercice.code_enregistre || '';
        }
    }

    // Mise à jour de l'information sur le nombre de soumissions restantes
    const soumissionsInfo = document.getElementById(`soumissions-info-${exercice.id}`);
    if (soumissionsInfo) {
        const soumissionsRestantes = exercice.nb_soumissions_restantes;
        soumissionsInfo.textContent = `Soumissions restantes : ${soumissionsRestantes}`;
    }

    // Gérer l'activation ou la désactivation du bouton de soumission
    // en fonction du nombre de soumissions restantes
    const submissionButton = document.getElementById(`btn-submit-participant-${exercice.id}`);
    if (submissionButton) {
        submissionButton.disabled = exercice.nb_soumissions_restantes <= 0;
    }
}

export function mettreAJourBoutonSoumission(exercice) {
    // Vérifie si le nombre de soumissions restantes atteint zéro
    if (exercice.nb_soumissions_restantes === 0) {
        // Désactive le bouton de soumission si aucune soumission n'est restante
        desactiveBoutonSoumission(exercice.id);
    } else {
        // Sinon, assurez-vous que le bouton est activé
        activeBoutonSoumission(exercice.id);
    }
}


/**
 * Met à jour les valeurs associées à un exercice donné.
 * @param {Object} exercice - L'objet contenant les informations de l'exercice.
 */
export function mettreAJourExercice(exercice) {
    mettreAJourValeursExercice(exercice);
    mettreAJourBoutonSoumission(exercice);
}

function soumettreReponse(exercice) {
    const exerciseId = exercice.id
    // Récupération des données de réponse
    const codeSubmission = document.getElementById(`code-submission-${exerciseId}`) ?
        document.getElementById(`code-submission-${exerciseId}`).value : '';
    const instanceResponse = document.getElementById(`instance-response-${exerciseId}`) ?
        document.getElementById(`instance-response-${exerciseId}`).value : '';

    // Créer l'objet de données à envoyer
    const data = {
        exercice_id: exerciseId,
        code_soumis: codeSubmission,
        solution_instance: instanceResponse
    };

    desactiveBoutonSoumission(exerciseId);

    fetch('/epreuve/soumettre_reponse/', {
        method: 'POST',
        body: JSON.stringify(data),
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'Content-Type': 'application/json'
        }
    })
        .then(response => response.json())
        .then(data => {
            activeBoutonSoumission(exerciseId);

            // Met à jour l'objet exercice avec les nouvelles données reçues
            exercice.nb_soumissions_restantes = data.nb_soumissions_restantes;
            exercice.code_enregistre = data.code_enregistre;
            exercice.reponse_jeu_de_test_enregistree = data.reponse_jeu_de_test_enregistree;

            // Appelle mettreAJourValeursExercice avec l'objet exercice mis à jour
            mettreAJourExercice(exercice);
            if (exercice.retour_en_direct) {
                mettreAJourIndicateur(exerciseId, data.reponse_valide);
            }

        })
        .catch(error => {
            console.error('Erreur:', error);
            activeBoutonSoumission(exerciseId);
        });}

