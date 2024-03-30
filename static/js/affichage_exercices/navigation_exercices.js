import {indicateurExoCourants} from "./indicateur_etat.js";

export let currentExerciseIndex = 0;

export function nextExercise(exercices) {
    currentExerciseIndex++;
    indicateurExoCourants(exercices[currentExerciseIndex].id, exercices);
}

export function prevExercise(exercices) {
    if (currentExerciseIndex > 0) {
        currentExerciseIndex--;
        indicateurExoCourants(exercices[currentExerciseIndex].id, exercices);
    }
}
