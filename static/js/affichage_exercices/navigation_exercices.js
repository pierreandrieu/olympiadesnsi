import {indicateurExoCourant} from "./indicateur_etat.js";

export let currentExerciseIndex = 0;

export function nextExercise(exercices) {
    currentExerciseIndex++;
    indicateurExoCourant(exercices[currentExerciseIndex].id, exercices);
}

export function prevExercise(exercices) {
    if (currentExerciseIndex > 0) {
        currentExerciseIndex--;
        indicateurExoCourant(exercices[currentExerciseIndex].id, exercices);
    }
}
