import {afficherExerciceQCM} from './exercice_qcm.js';
import {afficherExerciceProgrammation} from './exercice_programmation.js';

export function afficherExerciceActuel(exercice) {
    const container = document.getElementById('exercice-container');
    container.innerHTML = '';
    console.log("enter");
    switch (exercice.type_exercice) {
        case 'qcm':
            afficherExerciceQCM(exercice, container);
            break;
        case 'programmation':
            afficherExerciceProgrammation(exercice, container);
            break;
        default:
            console.log("default");
            break;
    }
}
