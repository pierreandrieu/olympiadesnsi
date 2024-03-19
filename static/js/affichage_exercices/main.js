import * as nav from './navigation_exercices.js';
import {creerElementsExercice, mettreAJourValeursExercice} from './exercice_programmation.js';
import {indicateurExoCourant, initIndicateursEtat} from "./indicateur_etat.js";

document.addEventListener('DOMContentLoaded', () => {
    // console.log("coucou");
    const exercices = JSON.parse(document.getElementById('exercises-data').textContent);
    console.log(exercices);
    const container = document.getElementById('exercice-container');
    let prevButton = document.getElementById('prev-exercise');
    let nextButton = document.getElementById('next-exercise');
    const unParUn = prevButton.dataset.unParUn === 'true';

    prevButton.addEventListener('click', () => {
        nav.prevExercise(exercices);
        creerElementsExercice(exercices[nav.currentExerciseIndex], container);
        mettreAJourValeursExercice(exercices[nav.currentExerciseIndex]);
        updateButtonStates(exercices);
    });

    nextButton.addEventListener('click', () => {
        nav.nextExercise(exercices);
        creerElementsExercice(exercices[nav.currentExerciseIndex], container);
        mettreAJourValeursExercice(exercices[nav.currentExerciseIndex]);
        updateButtonStates(exercices);
    });

    function updateButtonStates() {
        prevButton.disabled = nav.currentExerciseIndex === 0 || unParUn;
        nextButton.disabled = nav.currentExerciseIndex >= exercices.length - 1;
    }

    if (exercices.length > 0) {
        // console.log("oui!");
        initIndicateursEtat(exercices); // Cette fonction doit initialiser visuellement les indicateurs d'état pour tous les exercices
        // console.log(nav.currentExerciseIndex);
        creerElementsExercice(exercices[nav.currentExerciseIndex], container);
        // console.log("ok");
        mettreAJourValeursExercice(exercices[nav.currentExerciseIndex]);
        // console.log("ok2");
    }
    updateButtonStates();
    // console.log("ok3");
    console.log("INDIC = ");
    console.log(nav.currentExerciseIndex);
    console.log(exercices[nav.currentExerciseIndex].id);

    indicateurExoCourant(exercices[nav.currentExerciseIndex].id, exercices);
    // console.log("ok4");
});
