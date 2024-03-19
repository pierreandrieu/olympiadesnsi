function initialiserChronometre(tempsRestantDataId) {
    console.log("debut chrono");
    let elem = document.querySelector('script[type="application/json"]#' + tempsRestantDataId);
    console.log("elem = " + elem);
    let tempsRestant = JSON.parse(elem.textContent);
    console.log("temps restant " + tempsRestant);

    const intervalId = setInterval(function () {
        if (tempsRestant <= 0) {
            clearInterval(intervalId);
            document.getElementById('temps-restant').textContent = '00:00:00';
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

// Cette vérification va chercher l'élément de script qui contient les données JSON pour le temps restant
if (document.querySelector('script[type="application/json"]#temps-restant-data')) {
    initialiserChronometre('temps-restant-data');
}
