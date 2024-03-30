export function initIndicateursEtat(exercises, id_indicateur) {
    const etatExercicesContainer = document.getElementById(id_indicateur);
    exercises.forEach(exercise => {
        const indicateur = document.createElement('span');
        if(exercise.retour_en_direct) {
            if (exercise.reponse_jeu_de_test_enregistree === '' || exercise.reponse_jeu_de_test_enregistree === null) {
                indicateur.className = 'indic-exo-non-soumis fa-regular fa-circle-question fa-lg';
            }
            else
            {
                if (exercise.reponse_valide) {
                    indicateur.className = 'indic-exo-valide fa-regular fa-circle-check fa-lg';
                } else {
                    indicateur.className = 'indic-exo-invalide fa-regular fa-circle-xmark fa-lg';
                }
            }
        }
        else {
            indicateur.className = 'indic-exo-non-soumis fa-regular fa-circle-question fa-lg';
        }

        indicateur.id = `${id_indicateur}-${exercise.id}`;
        etatExercicesContainer.appendChild(indicateur);
    });
}

export function indicateurExoCourant(exoCourantId, exercises, id_indicateur) {
    let i = 0;
    exercises.forEach(exercise => {
        i += 1;
        let exo = document.getElementById(`${id_indicateur}-${exercise.id}`);

        exo.classList.remove('fa-solid');
        exo.classList.remove('fa-2xl');
        exo.classList.add('fa-regular');
        exo.classList.add('fa-lg');
    });
    let exoCourant = document.getElementById(`${id_indicateur}-${exoCourantId}`);

    exoCourant.classList.remove('fa-regular');
    exoCourant.classList.remove('fa-lg');
    exoCourant.classList.add('fa-solid');
    exoCourant.classList.add('fa-2xl');
}

export function mettreAJourIndicateur(exerciseId, isSuccess, id_indicateur) {
    const indicateur = document.getElementById(`${id_indicateur}-${exerciseId}`);
    if (isSuccess) {
        indicateur.classList.remove('indic-exo-non-soumis');
        indicateur.classList.remove('fa-circle-question');
        indicateur.classList.remove('indic-exo-invalide');
        indicateur.classList.remove('fa-circle-xmark');
        indicateur.classList.add('indic-exo-valide');
        indicateur.classList.add('fa-circle-check');
    } else {
        indicateur.classList.remove('indic-exo-non-soumis');
        indicateur.classList.remove('fa-circle-question');
        indicateur.classList.add('indic-exo-invalide');
        indicateur.classList.add('fa-circle-xmark');
        indicateur.classList.remove('indic-exo-valide');
        indicateur.classList.remove('fa-circle-check');
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

export function mettreAJourIndicateurs(exerciseId, isSuccess) {
    mettreAJourIndicateur(exerciseId, isSuccess, "etat-exercices")
    mettreAJourIndicateur(exerciseId, isSuccess, "etat-exercices2")
}