export function initIndicateursEtat(exercises, idIndicateur) {
    const etatExercicesContainer = document.getElementById(idIndicateur);
    exercises.forEach(exercise => {
        const indicateur = document.createElement('span');
        if(exercise.retour_en_direct) {
            if (exercise.reponse_jeu_de_test_enregistree === '' || exercise.reponse_jeu_de_test_enregistree === null) {
                indicateur.className = 'indic-exo-non-soumis fa-regular fa-circle-question fa-lg';
            }
            else
            {
                if (exercise.reponse_valide) {
                    if (!exercise.code_requis || (exercise.code_enregistre?.trim().length > 0)) {                        indicateur.className = 'indic-exo-valide fa-regular fa-circle-check fa-lg';
                    }
                    else {
                        indicateur.className = 'indic-exo-code-manquant fa-regular fa-pencil fa-lg';
                    }
                } else {
                    indicateur.className = 'indic-exo-invalide fa-regular fa-circle-xmark fa-lg';
                }
            }
        }
        else {
            indicateur.className = 'indic-exo-non-soumis fa-regular fa-circle-question fa-lg';
        }

        indicateur.id = `${idIndicateur}-${exercise.id}`;
        etatExercicesContainer.appendChild(indicateur);
    });
}

export function indicateurExoCourant(exoCourantId, exercises, idIndicateur) {
    let i = 0;
    exercises.forEach(exercise => {
        i += 1;
        let exo = document.getElementById(`${idIndicateur}-${exercise.id}`);

        exo.classList.remove('fa-solid');
        exo.classList.remove('fa-2xl');
        exo.classList.add('fa-regular');
        exo.classList.add('fa-lg');
    });
    let exoCourant = document.getElementById(`${idIndicateur}-${exoCourantId}`);

    exoCourant.classList.remove('fa-regular');
    exoCourant.classList.remove('fa-lg');
    exoCourant.classList.add('fa-solid');
    exoCourant.classList.add('fa-2xl');
}

export function mettreAJourIndicateur(exerciseId, isSuccess, idIndicateur, codeRempli, codeRequis) {
    const indicateur = document.getElementById(`${idIndicateur}-${exerciseId}`);
    indicateur.classList.remove(
        'indic-exo-non-soumis',
        'fa-circle-question',
        'indic-exo-invalide',
        'indic-exo-code-manquant',
        'fa-circle-xmark',
        'indic-exo-valide',
        'fa-circle-check',
        'fa-pencil'
    );

    if (isSuccess) {
        if (!codeRequis || codeRempli) {
            indicateur.classList.add('indic-exo-valide', 'fa-circle-check');
            indicateur.setAttribute('title', 'Félicitations, vous avez trouvé la bonne réponse à votre jeu de test !');
        } else {
            indicateur.classList.add('indic-exo-code-manquant', 'fa-pencil');
            indicateur.setAttribute('title', 'Code manquant : n’oubliez pas de soumettre votre code pour cet exercice.');
        }
    } else {
        indicateur.classList.add('indic-exo-invalide', 'fa-circle-xmark');
        indicateur.setAttribute('title', 'Vous n\'avez pas encore trouvé la bonne réponse à votre jeu de test.');
    }
}


export function initIndicateursEtats(exercises) {
    initIndicateursEtat(exercises, "etat-exercices");
    initIndicateursEtat(exercises, "etat-exercices2");
}

export function indicateurExoCourants(exoCourantId, exercises) {
    indicateurExoCourant(exoCourantId, exercises, "etat-exercices");
    indicateurExoCourant(exoCourantId, exercises, "etat-exercices2");
}

export function mettreAJourIndicateurs(exerciseId, isSuccess, codeRempli, codeRequis) {
    mettreAJourIndicateur(exerciseId, isSuccess, "etat-exercices", codeRempli, codeRequis);
    mettreAJourIndicateur(exerciseId, isSuccess, "etat-exercices2", codeRempli, codeRequis);
}
