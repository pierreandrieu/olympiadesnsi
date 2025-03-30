import * as nav from './navigation_exercices.js';
import {creerElementsExercice, mettreAJourValeursExercice} from './exercice_programmation.js';
import {
    indicateurExoCourants,
    initIndicateursEtats
} from "./indicateur_etat.js";

document.addEventListener('DOMContentLoaded', () => {
    const lectureSeule = document.body.dataset.lectureSeule === 'true';
    const exercices = JSON.parse(document.getElementById('exercises-data').textContent);
    const container = document.getElementById('exercice-container');

    // Nouvelle récupération : via attribut data-un-par-un sur <body>
    const unParUn = document.body.dataset.unParUn === 'true';

    // Navigation par boutons flottants
    const btnGauche = document.getElementById('btn-nav-left');
    const btnDroite = document.getElementById('btn-nav-right');

    btnGauche.addEventListener('click', () => {
        nav.prevExercise(exercices);
        creerElementsExercice(exercices[nav.currentExerciseIndex], container, lectureSeule);
        mettreAJourValeursExercice(exercices[nav.currentExerciseIndex]);
        updateButtonStates();
    });

    btnDroite.addEventListener('click', () => {
        nav.nextExercise(exercices);
        creerElementsExercice(exercices[nav.currentExerciseIndex], container, lectureSeule);
        mettreAJourValeursExercice(exercices[nav.currentExerciseIndex]);
        updateButtonStates();
    });

    function updateButtonStates() {
        btnGauche.style.display =
            (nav.currentExerciseIndex === 0 || unParUn) ? 'none' : 'inline-block';
        btnDroite.style.display =
            (nav.currentExerciseIndex >= exercices.length - 1) ? 'none' : 'inline-block';
    }

    if (exercices.length > 0) {
        creerElementsExercice(exercices[nav.currentExerciseIndex], container, lectureSeule);
        initIndicateursEtats(exercices);
        mettreAJourValeursExercice(exercices[nav.currentExerciseIndex]);
        indicateurExoCourants(exercices[nav.currentExerciseIndex].id, exercices);
    }

    updateButtonStates();

    function alignerBoutonsNavigation() {
        const container = document.querySelector('.exercise-box');
        const btnLeft = document.getElementById('btn-nav-left');
        const btnRight = document.getElementById('btn-nav-right');

        if (!container || !btnLeft || !btnRight) return;

        const rect = container.getBoundingClientRect();
        const offsetGauche = rect.left;
        const offsetDroite = window.innerWidth - rect.right;

        btnLeft.style.left = `${offsetGauche - 60}px`; // 60px pour l'espace
        btnRight.style.right = `${offsetDroite - 60}px`;
    }

// Aligner au chargement
    window.addEventListener('load', alignerBoutonsNavigation);
// Et au redimensionnement
    window.addEventListener('resize', alignerBoutonsNavigation);
});

// Pour le code highlight
document.addEventListener('DOMContentLoaded', (event) => {
    document.querySelectorAll('pre code').forEach((block) => {
        hljs.highlightElement(block);
    });
});

