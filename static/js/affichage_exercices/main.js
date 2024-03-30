import * as nav from './navigation_exercices.js';
import {creerElementsExercice, mettreAJourValeursExercice} from './exercice_programmation.js';
import {
    indicateurExoCourants,
    initIndicateursEtats
} from "./indicateur_etat.js";

document.addEventListener('DOMContentLoaded', () => {
    const exercices = JSON.parse(document.getElementById('exercises-data').textContent);
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
        creerElementsExercice(exercices[nav.currentExerciseIndex], container);
        initIndicateursEtats(exercices);
        mettreAJourValeursExercice(exercices[nav.currentExerciseIndex]);
    }
    updateButtonStates();
    indicateurExoCourants(exercices[nav.currentExerciseIndex].id, exercices);
});

document.addEventListener('DOMContentLoaded', (event) => {
  document.querySelectorAll('pre code').forEach((block) => {
    hljs.highlightBlock(block);
  });
});