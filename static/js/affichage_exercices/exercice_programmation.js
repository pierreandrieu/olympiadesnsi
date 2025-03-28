import {renderLatex} from './render_latex.js';
import {desactiveBoutonSoumission, activeBoutonSoumission}  from "./bouton_submit.js";
import {getCookie} from "./cookies.js";
import {mettreAJourIndicateurs} from "./indicateur_etat.js";
import {ajouterTesteurPython} from './python.js';

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
        // Ajoute une marge en bas pour créer un espace après l'énoncé
        enonceElement.style.marginBottom = '10px';
        container.appendChild(enonceElement);
    }

    // Vérifie et ajoute l'énoncé de code si présent
    if (exercice.enonce_code && exercice.enonce_code.trim().length > 0) {
        // Crée un paragraphe d'introduction pour le code
        const introCodeP = document.createElement('p');
        introCodeP.textContent = "Le code ci-dessous vous est fourni :";
        container.appendChild(introCodeP); // Ajoute le paragraphe au conteneur

        // Création du conteneur pour le bouton de copie
        const copyButtonContainer = document.createElement('div');
        const copyButton = document.createElement('button');
        copyButton.textContent = 'Copier le code fourni';
        copyButton.className = 'copy-code-button'; // Ajoutez une classe pour le style si nécessaire
        copyButtonContainer.appendChild(copyButton);
        container.appendChild(copyButtonContainer); // Ajoute le conteneur du bouton au conteneur principal

        const codeElement = document.createElement('pre');
        codeElement.className = 'pre-scrollable';
        const codeContent = document.createElement('code');
        codeContent.className = 'language-python';
        codeContent.textContent = exercice.enonce_code;
        codeElement.appendChild(codeContent);
        container.appendChild(codeElement); // Ajoute le bloc de code au conteneur

        // Fonction pour copier le texte dans le presse-papier
        copyButton.addEventListener('click', function() {
            const textToCopy = exercice.enonce_code.replace(/\n\n/g, '\n');
            navigator.clipboard.writeText(textToCopy).then(() => {
                // Afficher un message de confirmation ou changer brièvement le texte du bouton pour indiquer le succès de la copie
                copyButton.textContent = 'Copié!';
                setTimeout(() => copyButton.textContent = 'Copier', 2000); // Revenir au texte original après 2 secondes
            }).catch(err => {
                // Gérer l'erreur (par exemple, afficher un message d'erreur)
                console.error('Erreur lors de la copie du texte: ', err);
            });
        });
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

        // Création et ajout du bouton de copie
        const copyButton = document.createElement('button');
        copyButton.textContent = 'Copier le jeu de test';
        copyButton.className = 'copy-test-button'; // Ajoutez une classe pour le style si nécessaire
        jeuDeTestContainer.appendChild(copyButton);

        // Fonction pour copier le texte de l'instance du jeu de test dans le presse-papier
        copyButton.addEventListener('click', function() {
            navigator.clipboard.writeText(exercice.instance_de_test).then(() => {
                // Afficher un message de confirmation ou changer brièvement le texte du bouton pour indiquer le succès de la copie
                copyButton.textContent = 'Copié!';
                setTimeout(() => copyButton.textContent = 'Copier le jeu de test', 2000); // Revenir au texte original après 2 secondes
            }).catch(err => {
                // Gérer l'erreur (par exemple, afficher un message d'erreur)
                console.error('Erreur lors de la copie du texte: ', err);
            });
        });

        // Affichage de l'instance du jeu de test
        const jeuDeTestInstance = document.createElement('pre');
        jeuDeTestInstance.className = 'jeu-de-test-instance pre-scrollable';
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

        // Ajoute une section pour la réponse attendue si elle existe
        if (exercice.reponse_attendue) {
            // Création du conteneur pour la réponse attendue
            const reponseAttendueContainer = document.createElement('div');
            reponseAttendueContainer.className = 'reponse-attendue-container';

            // Ajout d'un texte explicatif pour la réponse attendue
            const reponseAttendueExplication = document.createElement('p');
            reponseAttendueExplication.textContent = 'Réponse attendue :';
            reponseAttendueContainer.appendChild(reponseAttendueExplication);

            // Affichage de la réponse attendue
            const reponseAttendueInstance = document.createElement('pre');
            reponseAttendueInstance.className = 'reponse-attendue-instance pre-scrollable';
            reponseAttendueInstance.textContent = exercice.reponse_attendue;
            reponseAttendueContainer.appendChild(reponseAttendueInstance);

            // Ajout du conteneur de la réponse attendue au conteneur principal
            container.appendChild(reponseAttendueContainer);
        }
    }

// Création du champ pour la soumission du code, si nécessaire
    if (exercice.code_a_soumettre) {
        const codeContainer = document.createElement('div');
        codeContainer.className = 'code-submission-container';

        // Ajout d'un texte explicatif pour l'insertion du code
        const codeExplication = document.createElement('p');
        codeExplication.textContent = 'Insérez ici votre code ayant permis de générer la réponse :';
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
        ajouterTesteurPython(container, exercice.code_enregistre || "");
    }


    // Affiche le nombre de soumissions encore possibles
    const soumissionsInfo = document.createElement('div');
    soumissionsInfo.className = 'soumissions-info';
    soumissionsInfo.id = `soumissions-info-${exercice.id}`;
    const soumissionsRestantes = exercice.nb_soumissions_restantes;
    soumissionsInfo.textContent = `Soumissions restantes (max 10 par minute): ${soumissionsRestantes}`;
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
    const urlSoumission = document.getElementById('url-soumission').textContent;
    const exerciseId = exercice.id;

    // Récupération des données saisies
    const codeSubmission = document.getElementById(`code-submission-${exerciseId}`)?.value || '';
    const instanceResponse = document.getElementById(`instance-response-${exerciseId}`)?.value || '';

    // Préparation des données à envoyer
    const data = {
        exercice_id: exerciseId,
        code_soumis: codeSubmission,
        solution_instance: instanceResponse
    };

    desactiveBoutonSoumission(exerciseId);

    fetch(urlSoumission, {
        method: 'POST',
        credentials: 'include',
        body: JSON.stringify(data),
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'Content-Type': 'application/json'
        }
    })
        .then(async response => {
            if (response.status === 429) {
                // Rediriger vers la page d'erreur ou afficher un message
                alert("Nous avons détecté un nombre élevé de soumissions en peu de temps." +
                    "Veuillez attendre quelques instants avant de soumettre à nouveau.")
                return;
            }
            const rawText = await response.text(); // on récupère le texte brut, qu’il soit JSON ou HTML

            try {
                const data = JSON.parse(rawText); // essaie de parser le JSON
                // Met à jour l'objet exercice avec les nouvelles données
                exercice.nb_soumissions_restantes = data.nb_soumissions_restantes;
                exercice.code_enregistre = data.code_enregistre;
                exercice.reponse_jeu_de_test_enregistree = data.reponse_jeu_de_test_enregistree;

                mettreAJourExercice(exercice);

                if (exercice.retour_en_direct) {
                    const codeRempli = exercice.code_enregistre && exercice.code_enregistre.trim().length > 0;
                    mettreAJourIndicateurs(exerciseId, data.reponse_valide, codeRempli);
                }

            } catch (err) {
                console.error("Erreur lors du parsing JSON :", err);
                console.error("Contenu non JSON reçu :", rawText);
            }

        })
        .catch(error => {
            console.error("Erreur lors de la soumission :", error);
            activeBoutonSoumission(exerciseId);
        });
}

