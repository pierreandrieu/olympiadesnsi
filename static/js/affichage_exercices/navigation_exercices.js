export let currentExerciseIndex = 0;

export function nextExercise() {
    currentExerciseIndex++;
}

export function prevExercise() {
    if (currentExerciseIndex > 0) {
        currentExerciseIndex--;
    }
}
