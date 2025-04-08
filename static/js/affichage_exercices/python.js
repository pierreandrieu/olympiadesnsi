export function ajouterTesteurPython(container, codeParDefaut = "") {
    const bloc = document.createElement("div");
    bloc.className = "testeur-python mt-3 p-2 border rounded bg-light";

    const titre = document.createElement("h5");
    titre.textContent = "Console python (utilisation de print obligatoires pour afficher)";
    titre.style.textAlign = "center";
    bloc.appendChild(titre);

    const sousTitre = document.createElement("div");
    sousTitre.className = "alert alert-info my-3 py-2 px-3";
    sousTitre.style.fontSize = "0.95em";
    sousTitre.innerHTML =
        "💡 <strong>Important :</strong> lorsque vous enregistrez et testez votre solution, <strong>le code et la sortie affichée sous la console sont enregistrés</strong>.<br>" +
        "Pour que votre réponse enregistrée soit considérée comme juste, <strong>seule la bonne réponse doit apparaître en sortie de la console.</strong> " +
        "Vous pouvez donc faire autant de <code>print()</code> que vous voulez pour tester, mais assurez-vous de n’afficher que la réponse attendue au moment de soumettre.";
    bloc.appendChild(sousTitre);

    const editorElement = document.createElement("textarea");
    bloc.appendChild(editorElement);

    const style = document.createElement('style');
    style.textContent = `
        .testeur-python .CodeMirror-gutters {
            width: 45px !important;
        }
        .testeur-python .CodeMirror-linenumber {
            padding: 0 5px 0 0 !important;
            text-align: right !important;
        }
        .testeur-python .CodeMirror-sizer {
            margin-left: 45px !important;
        }
        .testeur-python .CodeMirror-lines {
            padding-left: 4px !important;
        }
    `;
    document.head.appendChild(style);

    const editor = CodeMirror.fromTextArea(editorElement, {
        value: codeParDefaut,
        lineNumbers: true,
        mode: "python",
        theme: "default",
        indentUnit: 4,
        tabSize: 4,
        indentWithTabs: false,
        styleActiveLine: true,
        lineWrapping: true,
        viewportMargin: Infinity,
        extraKeys: {
            Tab: (cm) => {
                if (cm.somethingSelected()) {
                    cm.indentSelection("add");
                } else {
                    cm.replaceSelection("    ", "end");
                }
            },
            "Shift-Tab": (cm) => {
                cm.operation(() => {
                    const ranges = cm.listSelections();

                    for (const range of ranges) {
                        const from = range.from();
                        const to = range.to();

                        // Si aucune sélection
                        if (from.line === to.line && from.ch === to.ch) {
                            const line = cm.getLine(from.line);
                            const start = Math.max(0, from.ch - 4);
                            const beforeCursor = line.substring(start, from.ch);

                            // On retire jusqu'à 4 espaces ou une tab juste avant le curseur
                            const match = beforeCursor.match(/( {1,4}|\t)$/);
                            if (match) {
                                const len = match[0].length;
                                cm.replaceRange(
                                    "",
                                    {line: from.line, ch: from.ch - len},
                                    from
                                );
                            }
                        } else {
                            // Sélection sur plusieurs lignes : on désindente chaque ligne
                            const fromLine = from.line;
                            const toLine = to.line;

                            for (let i = fromLine; i <= toLine; i++) {
                                const line = cm.getLine(i);
                                const match = line.match(/^( {1,4}|\t)/);
                                if (match) {
                                    const len = match[0].length;
                                    cm.replaceRange(
                                        "",
                                        {line: i, ch: 0},
                                        {line: i, ch: len}
                                    );
                                }
                            }
                        }
                    }
                });
            }
        }
    });

    const codeNettoye = codeParDefaut.replace(/\u200B/g, '');
    editor.setValue(codeNettoye);

    setTimeout(() => {
        editor.refresh();
    }, 100);

    const bouton = document.createElement("button");
    bouton.textContent = "Exécutez votre code Python";
    bouton.className = "btn btn-secondary mb-2";
    bouton.style.display = "block";
    bouton.style.margin = "0 auto";
    bouton.style.marginTop = "10px";
    bloc.appendChild(bouton);

    const resultat = document.createElement("pre");
    resultat.textContent = "Résultat ou erreur ici…";
    resultat.className = "output-result py-2 px-3 bg-white border rounded";
    resultat.style.minHeight = "2em";
    bloc.appendChild(resultat);

    bouton.addEventListener("click", () => {
        resultat.textContent = "";
        const code = editor.getValue().replace(/\u200B/g, '');

        const outf = (text) => {
            resultat.textContent += text + "\n";
        };

        const builtinRead = (x) => {
            if (Sk.builtinFiles === undefined || Sk.builtinFiles["files"][x] === undefined) {
                throw `File not found: '${x}'`;
            }
            return Sk.builtinFiles["files"][x];
        };

        Sk.configure({output: outf, read: builtinRead});

        Sk.misceval.asyncToPromise(() =>
            Sk.importMainWithBody("<stdin>", false, code, true)
        )
            .then(() => {
                if (resultat.textContent.trim() === "") {
                    resultat.textContent = "(Aucun résultat)";
                }
            })
            .catch(err => {
                resultat.textContent = `❌ Erreur : ${err.toString()}`;
            });
    });

    container.appendChild(bloc);
}
