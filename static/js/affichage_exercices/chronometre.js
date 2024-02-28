function initialiserChronometre(tempsRestantDataId) {
    let tempsRestant = JSON.parse(document.getElementById(tempsRestantDataId).textContent);
    const intervalId = setInterval(function () {
        if (tempsRestant <= 0) {
            clearInterval(intervalId);
            document.getElementById('temps-restant').textContent = '00:00:00';
            // Logique à exécuter lorsque le temps est écoulé
        } else {
            tempsRestant--;
            const heures = Math.floor(tempsRestant / 3600);
            const minutes = Math.floor((tempsRestant % 3600) / 60);
            const secondes = tempsRestant % 60;
            document.getElementById('temps-restant').textContent =
                heures.toString().padStart(2, '0') + ':' +
                minutes.toString().padStart(2, '0') + ':' +
                secondes.toString().padStart(2, '0');
        }
    }, 1000);
}

if (document.getElementById('temps-restant-data')) {
    initialiserChronometre('temps-restant-data');
}
