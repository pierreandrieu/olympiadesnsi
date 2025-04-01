function toggleInput(i) {
    const choix1 = document.getElementById(`choix_${i}_1`);
    const input = document.getElementById(`anonymat_${i}`);
    if (choix1.checked) {
        input.style.display = '';
    } else {
        input.style.display = 'none';
        input.value = '';
    }
}

function cascadeDisable(index, disableFollowing) {
    const start = parseInt(index, 10);
    const total = 3; // nombre total de participants

    for (let i = start + 1; i <= total; i++) {
        const inputs = document.getElementsByName(`choix_${i}`);
        const anonymat = document.getElementById(`anonymat_${i}`);

        if (disableFollowing) {
            // Cocher automatiquement l'option "pas autant de participants"
            const choix4 = document.getElementById(`choix_${i}_4`);
            if (choix4) {
                choix4.checked = true;
            }
            anonymat.style.display = 'none';
            anonymat.value = '';
        }

        // Activer ou désactiver toutes les options
        inputs.forEach(input => {
            if (input.value !== "4") {
                input.disabled = disableFollowing;
            }
        });
    }
}