import {renderLatex} from './render_latex.js';
import {desactiveBoutonSoumission, activeBoutonSoumission} from "./bouton_submit.js";
import {getCookie} from "./cookies.js";
import {mettreAJourIndicateurs} from "./indicateur_etat.js";
import {ajouterTesteurPython} from './python.js';

/**
 * Crée dynamiquement les éléments d'un exercice et les insère dans le conteneur fourni.
 * Gère les cas Python avec console, exos avec ou sans jeu de test, ou dans un autre langage.
 * @param {Object} exercice - L'objet contenant les informations de l'exercice.
 * @param {HTMLElement} container - Le conteneur dans lequel insérer les éléments de l'exercice.
 */
export function creerElementsExercice(exercice, container, lectureSeule = false) {
    container.innerHTML = '';

    const titleElement = document.createElement('h2');
    titleElement.textContent = exercice.titre;
    titleElement.style.textAlign = "center";
    titleElement.style.marginBottom = "2rem";
    container.appendChild(titleElement);


    if (exercice.enonce?.trim()) {
        const enonceElement = document.createElement('div');
        renderLatex(exercice.enonce, enonceElement);
        enonceElement.style.marginBottom = '10px';
        container.appendChild(enonceElement);
    }

    if (exercice.enonce_code?.trim()) {
        const introCodeP = document.createElement('p');
        introCodeP.textContent = "Le code ci-dessous vous est fourni :";
        container.appendChild(introCodeP);

        const copyButtonContainer = document.createElement('div');
        const copyButton = document.createElement('button');
        copyButton.textContent = 'Copier le code fourni';
        copyButton.className = 'copy-code-button';
        copyButtonContainer.appendChild(copyButton);
        container.appendChild(copyButtonContainer);

        const codeElement = document.createElement('pre');
        codeElement.className = 'pre-scrollable';
        const codeContent = document.createElement('code');
        codeContent.className = 'language-python';
        codeContent.textContent = exercice.enonce_code;
        codeElement.appendChild(codeContent);
        container.appendChild(codeElement);

        copyButton.addEventListener('click', function () {
            const textToCopy = exercice.enonce_code.replace(/\n\n/g, '\n');
            navigator.clipboard.writeText(textToCopy).then(() => {
                copyButton.textContent = 'Copié!';
                setTimeout(() => copyButton.textContent = 'Copier', 2000);
            }).catch(err => {
                console.error('Erreur lors de la copie du texte: ', err);
            });
        });
    }

    const utiliseConsolePython = exercice.code_a_soumettre === 'python';

    // -- Affichage du jeu de test avant la console --
    if (exercice.avec_jeu_de_test) {
        const jeuDeTestContainer = document.createElement('div');
        jeuDeTestContainer.className = 'jeu-de-test-container';

        const label = document.createElement('p');
        label.textContent = 'Votre jeu de test :';
        jeuDeTestContainer.appendChild(label);

        const copyButton = document.createElement('button');
        copyButton.textContent = 'Copier le jeu de test';
        copyButton.className = 'copy-test-button';
        jeuDeTestContainer.appendChild(copyButton);

        copyButton.addEventListener('click', function () {
            navigator.clipboard.writeText(exercice.instance_de_test).then(() => {
                copyButton.textContent = 'Copié!';
                setTimeout(() => copyButton.textContent = 'Copier le jeu de test', 2000);
            }).catch(err => {
                console.error('Erreur lors de la copie du texte: ', err);
            });
        });

        const jeuDeTestInstance = document.createElement('pre');
        jeuDeTestInstance.className = 'jeu-de-test-instance pre-scrollable';
        jeuDeTestInstance.textContent = exercice.instance_de_test;
        jeuDeTestContainer.appendChild(jeuDeTestInstance);

        container.appendChild(jeuDeTestContainer);

        if (!utiliseConsolePython) {
            const responseContainer = document.createElement('div');
            responseContainer.className = 'instance-response-container';
            const reponseLabel = document.createElement('p');
            reponseLabel.textContent = 'La solution du jeu de test :';
            responseContainer.appendChild(reponseLabel);

            const textareaReponse = document.createElement('textarea');
            textareaReponse.id = `instance-response-${exercice.id}`;
            textareaReponse.placeholder = 'Votre réponse ici';
            textareaReponse.rows = 3;
            textareaReponse.className = 'form-control';
            textareaReponse.value = exercice.reponse_jeu_de_test_enregistree || '';

            textareaReponse.addEventListener('keydown', function (e) {
                if (e.key === 'Tab') {
                    e.preventDefault();
                    const start = this.selectionStart;
                    const end = this.selectionEnd;
                    const value = this.value;
                    const before = value.substring(0, start);
                    const selection = value.substring(start, end);
                    const after = value.substring(end);
                    const lines = selection.split('\n');
                    if (e.shiftKey) {
                        const updatedLines = lines.map(line => line.replace(/^ {1,4}/, ''));
                        const newText = updatedLines.join('\n');
                        this.value = before + newText + after;
                        this.selectionStart = start;
                        this.selectionEnd = start + newText.length;
                    } else {
                        const updatedLines = lines.map(line => '    ' + line);
                        const newText = updatedLines.join('\n');
                        this.value = before + newText + after;
                        this.selectionStart = start;
                        this.selectionEnd = start + newText.length;
                    }
                }
            });

            responseContainer.appendChild(textareaReponse);
            container.appendChild(responseContainer);
        }
    }

    // Console Python
    if (utiliseConsolePython) {
        const consoleWrapper = document.createElement('div');
        consoleWrapper.id = `console-python-${exercice.id}`;
        container.appendChild(consoleWrapper);
        ajouterTesteurPython(consoleWrapper, exercice.code_enregistre || "");

        // Centrage du titre et du bouton sera géré dans `ajouterTesteurPython`
    }

    // Réponse attendue
    if (exercice.reponse_attendue) {
        const bloc = document.createElement('div');
        bloc.className = 'reponse-attendue-container';
        const label = document.createElement('p');
        label.textContent = 'Réponse attendue :';
        const contenu = document.createElement('pre');
        contenu.className = 'reponse-attendue-instance pre-scrollable';
        contenu.textContent = exercice.reponse_attendue;
        bloc.appendChild(label);
        bloc.appendChild(contenu);
        container.appendChild(bloc);
    }

    if (exercice.code_a_soumettre === 'autre') {
        const codeContainer = document.createElement('div');
        codeContainer.className = 'code-submission-container';
        const label = document.createElement('p');
        label.textContent = 'Insérez ici votre code :';
        codeContainer.appendChild(label);
        const textarea = document.createElement('textarea');
        textarea.id = `code-submission-${exercice.id}`;
        textarea.placeholder = 'Votre code ici';
        textarea.textContent = exercice.code_enregistre || '';
        codeContainer.appendChild(textarea);
        container.appendChild(codeContainer);
    }

    // Suppression de l'ancien bloc "soumissions restantes"
    // Création du bouton avec le compteur intégré
    if (exercice.nb_soumissions_restantes > 0) {
        const btnContainer = document.createElement('div');
        btnContainer.style.textAlign = 'center';
        const btn = document.createElement('button');
        btn.id = `btn-submit-participant-${exercice.id}`;
        btn.className = 'btn nav-btn';
        btn.textContent = `Sauvegarder et tester mes réponses (${exercice.nb_soumissions_restantes} restants)`;

        if (lectureSeule) {
            btn.disabled = true;
            btn.title = "Désactivé en mode jury (lecture seule)";
        } else {
            btn.addEventListener('click', function () {
                soumettreReponse(exercice);
            });
        }

        btnContainer.appendChild(btn);
        container.appendChild(btnContainer);
    }
}


function soumettreReponse(exercice) {
    const urlSoumission = document.getElementById('url-soumission').textContent;
    const exerciseId = exercice.id;

    let codeSubmission = '';
    let instanceResponse = '';

    if (exercice.code_a_soumettre === 'python') {
        const codeLines = document.querySelectorAll(`#console-python-${exerciseId} .CodeMirror-line`);
        codeSubmission = Array.from(codeLines)
            .map(line => line.textContent.replace(/\u200B/g, ''))
            .join('\n');

        const outputElement = document.querySelector(`#console-python-${exerciseId} .output-result`);
        instanceResponse = outputElement?.textContent.replace(/\u200B/g, '').trim() || '';
    } else {
        codeSubmission = document.getElementById(`code-submission-${exerciseId}`)?.value || '';
        instanceResponse = document.getElementById(`instance-response-${exerciseId}`)?.value || '';
    }

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
            if (response.status === 413) {
                alert("⚠️ Votre code ou votre réponse est trop long. Merci de raccourcir avant de soumettre.");
                return;
            }
            if (response.status === 429) {
                alert("Trop de soumissions. Veuillez patienter un peu et réessayez.");
                return;
            }

            const rawText = await response.text();
            try {
                const data = JSON.parse(rawText);
                exercice.nb_soumissions_restantes = data.nb_soumissions_restantes;
                const btn = document.getElementById(`btn-submit-participant-${exerciseId}`);
                if (btn) {
                    btn.textContent = `Sauvegarder et tester mes réponses (${data.nb_soumissions_restantes} restants)`;
                }
                exercice.code_enregistre = data.code_enregistre;
                exercice.reponse_jeu_de_test_enregistree = data.reponse_jeu_de_test_enregistree;
                mettreAJourExercice(exercice);
                if (exercice.retour_en_direct) {
                    const codeRempli = exercice.code_enregistre && exercice.code_enregistre.trim().length > 0;
                    mettreAJourIndicateurs(exerciseId, data.reponse_valide, codeRempli, data.code_requis);
                }
            } catch (err) {
                console.error("Erreur JSON :", err);
                console.error("Contenu reçu :", rawText);
            }
        })
        .catch(error => {
            console.error("Erreur soumission :", error);
            activeBoutonSoumission(exerciseId);
        });
}

export function mettreAJourValeursExercice(exercice) {
    if (exercice.avec_jeu_de_test) {
        const inputReponse = document.getElementById(`instance-response-${exercice.id}`);
        if (inputReponse) {
            inputReponse.value = exercice.reponse_jeu_de_test_enregistree || '';
        }
    }
    if (exercice.code_a_soumettre === 'autre') {
        const textarea = document.getElementById(`code-submission-${exercice.id}`);
        if (textarea) {
            textarea.value = exercice.code_enregistre || '';
        }
    }
    const info = document.getElementById(`soumissions-info-${exercice.id}`);
    if (info) {
        info.textContent = `Soumissions restantes : ${exercice.nb_soumissions_restantes}`;
    }
    const btn = document.getElementById(`btn-submit-participant-${exercice.id}`);
    if (btn) {
        btn.disabled = exercice.nb_soumissions_restantes <= 0;
    }
}

export function mettreAJourBoutonSoumission(exercice) {
    if (exercice.nb_soumissions_restantes === 0) {
        desactiveBoutonSoumission(exercice.id);
    } else {
        activeBoutonSoumission(exercice.id);
    }
}

export function mettreAJourExercice(exercice) {
    mettreAJourValeursExercice(exercice);
    mettreAJourBoutonSoumission(exercice);
}
