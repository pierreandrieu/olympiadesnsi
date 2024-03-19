export function initIndicateursEtat(exercises) {
    const etatExercicesContainer = document.getElementById('etat-exercices');
    exercises.forEach(exercise => {
        const indicateur = document.createElement('span');
        if(exercise.retour_en_direct) {
            if(exercise.reponse_valide) {
                indicateur.className = 'indic-exo-valide fa-regular fa-circle-check fa-lg';
            }
            else {
                indicateur.className = 'indic-exo-invalide fa-regular fa-circle-xmark fa-lg';
            }
        }
        else {
            indicateur.className = 'indic-exo-non-soumis fa-regular fa-circle-question fa-lg';
        }

        indicateur.id = `indic-exo-${exercise.id}`;
        etatExercicesContainer.appendChild(indicateur);
    });
}

export function indicateurExoCourant(exoCourantId, exercises) {
    console.log("enter indicateur exo courant");
    let i = 0;
    exercises.forEach(exercise => {
        console.log("boucle i = " + i);
        console.log(exercise);
        i += 1;
        let exo = document.getElementById(`indic-exo-${exercise.id}`);
        console.log("exo = " + exo);
        exo.classList.remove('fa-solid');
        exo.classList.remove('fa-2xl');
        exo.classList.add('fa-regular');
        exo.classList.add('fa-lg');
        console.log(exo.classList);
    });
    console.log("end");
    console.log("exo courant = ");
    let exoCourant = document.getElementById(`indic-exo-${exoCourantId}`);
    console.log(exoCourant.id);
    console.log(exoCourant.textContent);

    exoCourant.classList.remove('fa-regular');
    exoCourant.classList.remove('fa-lg');
    exoCourant.classList.add('fa-solid');
    exoCourant.classList.add('fa-2xl');
    console.log(exoCourant.classList);

}

export function mettreAJourIndicateur(exerciseId, isSuccess) {
    const indicateur = document.getElementById(`indic-exo-${exerciseId}`);
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
