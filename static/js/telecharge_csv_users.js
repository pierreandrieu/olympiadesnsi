document.addEventListener('DOMContentLoaded', function () {
    const bouton = document.getElementById('btn-telecharger');
    const form = document.getElementById('downloadForm');

    bouton.addEventListener('click', function () {
        form.submit();
    });
});