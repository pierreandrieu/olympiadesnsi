export function ajouterTesteurPython(container, codeParDefaut = "") {
    const bloc = document.createElement("div");
    bloc.className = "testeur-python mt-3 p-2 border rounded bg-light";

    const titre = document.createElement("h5");
    titre.textContent = "Console python pour tester vos codes localement (non enregistré)";
    bloc.appendChild(titre);

    const editorElement = document.createElement("textarea");
    bloc.appendChild(editorElement);

    // Ajout d'un style personnalisé pour corriger l'overlap
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
                if (cm.somethingSelected()) {
                    cm.indentSelection("subtract");
                } else {
                    const cursor = cm.getCursor();
                    const line = cm.getLine(cursor.line);
                    const newLine = line.replace(/^ {1,4}/, "");
                    cm.replaceRange(newLine, {line: cursor.line, ch: 0}, {line: cursor.line, ch: line.length});
                }
            }
        }
    });

    editor.setValue(codeParDefaut);

    // Forcer un rafraîchissement après le rendu initial
    setTimeout(() => {
        editor.refresh();
    }, 100);

    const bouton = document.createElement("button");
    bouton.textContent = "Exécuter";
    bouton.className = "btn btn-secondary mb-2";
    bloc.appendChild(bouton);

    const resultat = document.createElement("pre");
    resultat.textContent = "Résultat ou erreur ici…";
    resultat.className = "output-result py-2 px-3 bg-white border rounded";
    resultat.style.minHeight = "2em";
    bloc.appendChild(resultat);

    bouton.addEventListener("click", () => {
        // Le reste du code reste inchangé...
        const code = editor.getValue();
        resultat.textContent = "";

        const outf = (text) => {
            resultat.textContent += text + "\n";
        };

        const builtinRead = (x) => {
            if (Sk.builtinFiles === undefined || Sk.builtinFiles["files"][x] === undefined) {
                throw `File not found: '${x}'`;
            }
            return Sk.builtinFiles["files"][x];
        };

        Sk.configure({
            output: outf,
            read: builtinRead
        });

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
