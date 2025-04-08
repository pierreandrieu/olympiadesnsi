# locustfile.py
from locust import HttpUser, task, between
from bs4 import BeautifulSoup
import json
import random
import csv
import os

CHEMIN_CSV = "utilisateurs.csv"  # Fichier généré juste avant par la commande Django


def charger_utilisateurs():
    chemin = os.path.join(os.path.dirname(__file__), CHEMIN_CSV)
    with open(chemin, newline='') as f:
        reader = csv.reader(f)
        return list(reader)


UTILISATEURS = charger_utilisateurs()
if not UTILISATEURS:
    raise Exception("Aucun utilisateur trouvé dans le fichier CSV")


class OlympiadesUser(HttpUser):
    wait_time = between(2, 4)

    def on_start(self):
        self.username, self.password, self.hash_epreuve_id = random.choice(UTILISATEURS)
        self.fake_ip = f"192.168.0.{random.randint(1, 254)}"  # ou toute plage factice

        # Récupération de la page de login
        response = self.client.get("/login/participant/")
        soup = BeautifulSoup(response.text, "html.parser")
        csrf_input = soup.find("input", attrs={"name": "csrfmiddlewaretoken"})
        if csrf_input is None:
            print(f"[{self.username}] ❌ Aucun champ CSRF trouvé sur /login/participant/")
            return

        csrf_token = csrf_input["value"]

        # Données de connexion
        data = {
            "username": self.username,
            "password": self.password,
            "csrfmiddlewaretoken": csrf_token,
        }
        headers = {
            "Referer": self.client.base_url + "/login/participant/",
            "X-Forwarded-For": self.fake_ip
        }

        response = self.client.post("/login/participant/", data=data, headers=headers)

        if "Se connecter" in response.text or "Identifiant ou mot de passe incorrect" in response.text:
            print(f"[{self.username}] ❌ Échec de connexion")
        else:
            print(f"[{self.username}] ✅ Connecté")
            self.charger_exercices()

    def charger_exercices(self):
        response = self.client.get(f"/epreuve/{self.hash_epreuve_id}/")
        try:
            start = response.text.index("exercices_json = JSON.parse('") + len("exercices_json = JSON.parse('")
            end = response.text.index("');", start)
            raw_json = response.text[start:end].encode('utf-8').decode('unicode_escape')
            exercices = json.loads(raw_json)
            self.exercice_ids = [ex["id"] for ex in exercices]
        except Exception as e:
            print(f"[{self.username}] ⚠️ Erreur lors de l'extraction des exercices : {e}")
            self.exercice_ids = []

    @task
    def soumettre_un_exercice(self):
        if not hasattr(self, 'exercice_ids') or not self.exercice_ids:
            return

        exercice_id = random.choice(self.exercice_ids)
        payload = {
            "exercice_id": exercice_id,
            "code_soumis": f"print('Soumission de {self.username}')",
            "solution_instance": f"Resultat de {self.username}"
        }
        self.client.post(
            f"/{self.hash_epreuve_id}/soumettre/",
            json=payload,
            name="Soumission exercice"
        )
