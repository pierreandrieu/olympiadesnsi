/**
 * Render LaTeX content within a specified container.
 * @param {string} latex - The LaTeX string to be rendered.
 * @param {HTMLElement} container - The container where the LaTeX should be rendered.
 */
export function renderLatex(latex, container) {
    const latexContainer = document.createElement('div');
    latexContainer.className = 'latex-content';
    latexContainer.innerHTML = latex;
    container.appendChild(latexContainer);

    MathJax.typesetPromise([latexContainer]).then(() => {
        console.log('LaTeX rendered successfully.');
    }).catch((err) => {
        console.error('Erreur de rendu LaTeX:', err);
    });
}
