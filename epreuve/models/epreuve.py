from typing import List, Iterable, Optional, Set, TYPE_CHECKING, cast
from django.core.cache import cache
from django.db import models, transaction
from django.utils import timezone
from django.utils.text import slugify
from django.contrib.auth.models import User
from django.db.models import CheckConstraint, Q, F, QuerySet, Subquery
from epreuve.utils import get_cache_key_liste_epreuves_publiques
from inscription.models import GroupeParticipant, GroupeParticipeAEpreuve, InscriptionDomaine
from olympiadesnsi.constants import MAX_TAILLE_NOM
from olympiadesnsi.utils import encode_id
if TYPE_CHECKING:
    from epreuve.models import Exercice, UserExercice, UserEpreuve, JeuDeTest


class Epreuve(models.Model):
    nom = models.CharField(max_length=MAX_TAILLE_NOM)
    code = models.CharField(max_length=255, unique=True, blank=False, null=False)
    date_debut = models.DateTimeField(null=False, blank=False)
    date_fin = models.DateTimeField(null=False, blank=False)
    duree = models.IntegerField(null=True)  # Durée en minutes
    referent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='epreuve_referent')
    exercices_un_par_un = models.BooleanField(default=False)
    temps_limite = models.BooleanField(default=False)
    inscription_externe = models.BooleanField(default=False)
    groupes_participants = models.ManyToManyField(GroupeParticipant, related_name='epreuves',
                                                  through='inscription.GroupeParticipeAEpreuve')
    comite = models.ManyToManyField(User, related_name='epreuves_comite', through='MembreComite')
    annale = models.ForeignKey(
        'self',  # auto-référence
        on_delete=models.SET_NULL,  # si l’annale est supprimée, ne casse pas tout
        null=True,
        blank=True,
        related_name='epreuves_associees'
    )

    @property
    def hashid(self) -> str:
        """
        Renvoie l'identifiant hashé de l'épreuve à utiliser dans les URLs.

        Returns:
            str: identifiant encodé (ex: pour usage dans les URLs).
        """
        return encode_id(self.id)

    @property
    def inscrits(self) -> QuerySet[User]:
        """
        Retourne les utilisateurs qui sont membres des groupes inscrits à cette épreuve.

        Returns:
            QuerySet[User]: Tous les participants effectivement inscrits via des groupes.
        """
        return User.objects.filter(appartenances__groupe__epreuves=self).distinct()

    def get_exercices(self) -> QuerySet['Exercice']:
        """
        Renvoie tous les exercices associés à cette épreuve.

        Returns:
            QuerySet[Exercice]: Un QuerySet contenant les exercices associés à l'épreuve.
        """
        return self.exercices.all()

    # Dans la classe Epreuve :
    def assigner_jeux_tests_exercices(self) -> None:
        """
        Attribue un jeu de test à chaque UserExercice pour tous les exercices de l’épreuve.

        Ne fait l’attribution que pour les exercices configurés avec un jeu de test.
        """
        for exercice in self.get_exercices():
            exercice.assigner_jeux_de_test()

    def inscrire_participants(self, participants: Iterable[User]) -> None:
        """
        Inscrit une liste de participants à l'épreuve et à tous les exercices associés.
        Si un exercice utilise des jeux de test, ceux-ci sont attribués de manière cyclique.

        Args:
            participants (Iterable[User]): Liste des utilisateurs à inscrire à l’épreuve.
        """

        exercices: List[Exercice] = list(self.get_exercices())
        user_epreuves_to_create: List[UserEpreuve] = []
        user_exercices_to_create: List[UserExercice] = []

        with transaction.atomic():
            # Étape 1 : création des UserEpreuve et UserExercice
            for user in participants:
                user_epreuves_to_create.append(UserEpreuve(participant=user, epreuve=self))
                for exercice in exercices:
                    user_exercices_to_create.append(UserExercice(participant=user, exercice=exercice))

            # Insertion en masse
            UserEpreuve.objects.bulk_create(user_epreuves_to_create, ignore_conflicts=True)
            UserExercice.objects.bulk_create(user_exercices_to_create, ignore_conflicts=True)

            # Étape 2 : attribution des jeux de test pour les exercices qui en ont
            for exercice in exercices:
                if not exercice.avec_jeu_de_test:
                    continue

                jeux: List[JeuDeTest] = list(exercice.get_jeux_de_test())
                if not jeux:
                    continue

                user_exercices = UserExercice.objects.filter(exercice=exercice, participant__in=participants)
                user_exercices_to_update: List[UserExercice] = []

                i = 0
                for ue in user_exercices:
                    if ue.jeu_de_test:
                        continue  # ne pas écraser un jeu déjà assigné
                    ue.jeu_de_test = jeux[i % len(jeux)]
                    i += 1
                    user_exercices_to_update.append(ue)

                UserExercice.objects.bulk_update(user_exercices_to_update, ['jeu_de_test'])
            self._maj_cache_nb_participants_epreuve(len(participants))

    def inscrire_groupe(self, groupe: GroupeParticipant) -> None:
        """
        Inscrit tous les membres d’un groupe à cette épreuve et à ses exercices associés.

        Cette méthode crée automatiquement les entrées `UserEpreuve` et `UserExercice`,
        ainsi que les jeux de test si nécessaire, pour chaque participant du groupe.

        Args:
            groupe (GroupeParticipant): Le groupe à inscrire.
        """
        GroupeParticipeAEpreuve.objects.get_or_create(epreuve=self, groupe=groupe)

        self.inscrire_participants(groupe.participants())

    def est_close(self) -> bool:
        """
        Renvoie True SSI l'épreuve est close
        Returns: True SSI l'épreuve est close

        """
        return self.date_fin < timezone.now()

    def pas_commencee(self):
        """
        Détermine si l'épreuve n'a pas encore commencé.

        Returns:
            bool: True si l'épreuve n'a pas encore commencé, False autrement.
        """
        # timezone.now() donne l'heure actuelle de manière "aware" en fonction des paramètres de timezone de Django
        return self.date_debut > timezone.now()

    def compte_participants_inscrits(self) -> int:
        """
        Retourne le nombre total d’utilisateurs inscrits à cette épreuve
        via les groupes de participants associés.

        Returns:
            int: Le nombre total de participants inscrits.
        """
        cache_key: str = f"epreuve_{self.id}_nombre_participants"

        cached: Optional[int] = cache.get(cache_key)
        if cached is not None:
            return cached

        total: int = (
                self.groupes_participants.annotate(nb=models.Count("membres"))
                .aggregate(total=models.Sum("nb"))
                .get("total") or 0
        )

        cache.set(cache_key, total, timeout=None)  # Pas d’expiration automatique
        return total

    def a_pour_membre_comite(self, user: User) -> bool:
        """
        Détermine si l'utilisateur donné est un membre du comité d'organisation de cette épreuve.

        Args:
            user (User): L'utilisateur à vérifier.

        Returns:
            bool: True si l'utilisateur est membre du comité, False autrement.
        """
        # On utilise `self.comite` pour accéder directement à la relation ManyToMany via le modèle intermédiaire
        # et on vérifie si l'utilisateur est dans la liste des membres du comité.
        return self.comite.filter(id=user.id).exists()

    def doit_demander_identifiants(self) -> bool:
        """
        Retourne True SSI on veut récupérer, au moment de la première connexion pour
        une épreuve d'olympiades, les identifiants de l'épreuve papier.
        :return:
        """
        return ("lympiade" in self.nom and "2025" in self.nom and "entrainement" not in self.nom
                and "annale" not in self.nom and self.referent.username == "pierre.andrieu")

    @staticmethod
    def liste_epreuves_publiques() -> QuerySet['Epreuve']:
        """
        Renvoie toutes les épreuves accessibles en inscription externe,
        c’est-à-dire ouvertes au public sans authentification préalable.

        Returns:
            QuerySet[Epreuve]: Un queryset contenant toutes les épreuves publiques.
        """
        return Epreuve.objects.filter(inscription_externe=True)

    def desinscrire_groupe(self, groupe: GroupeParticipant) -> None:
        """
        Désinscrit tous les membres d’un groupe de cette épreuve.
        Cela supprime :
          - les UserExercice liés
          - les UserEpreuve correspondants
          - le lien dans GroupeParticipeAEpreuve
        Et met à jour le cache du nombre de participants.
        """
        participants: QuerySet[User] = groupe.participants()

        user_epreuves = UserEpreuve.objects.filter(epreuve=self, participant__in=participants)

        exercice_ids = list(self.exercices.values_list('id', flat=True))

        UserExercice.objects.filter(
            exercice_id__in=exercice_ids,
            participant__in=user_epreuves.values_list('participant', flat=True)
        ).delete()

        user_epreuves.delete()

        GroupeParticipeAEpreuve.objects.filter(epreuve=self, groupe=groupe).delete()

        self._maj_cache_nb_participants_epreuve(-groupe.get_nombre_participants())

    def _maj_cache_nb_participants_epreuve(self, delta: int) -> None:
        """
        Met à jour le cache du nombre total de participants inscrits à cette épreuve
        en y ajoutant (ou en retirant) `delta`. Si le cache n'existe pas, il est initialisé
        à partir de la méthode `compte_participants_inscrits`.

        Args:
            delta (int): Le nombre de participants à ajouter ou retirer du total.
                         Peut être négatif.
        """
        cache_key: str = f"epreuve_{self.id}_nombre_participants"
        valeur_cachee: int = cache.get(cache_key)

        if valeur_cachee is not None:
            nouveau_total: int = max(0, valeur_cachee + delta)  # pas de valeur négative
        else:
            nouveau_total: int = self.compte_participants_inscrits()

        cache.set(cache_key, nouveau_total, timeout=None)

    def __str__(self):
        return self.nom

    def save(self, *args, **kwargs) -> None:
        """
        Sauvegarde le modèle `Epreuve` avec les étapes suivantes :
        - Effectue un nettoyage à la création (via `clean()`).
        - Sauvegarde les champs modifiés.
        - Génère ou met à jour le champ `code` basé sur `nom` et `id`.
        - Invalide le cache des épreuves publiques si le champ `inscription_externe` a changé.
        """
        is_new: bool = self.pk is None

        # Avant sauvegarde, stocke l’état initial du champ d’intérêt
        anciennement_publique: bool = False
        if not is_new:
            try:
                anciennement_publique = type(self).objects.get(pk=self.pk).inscription_externe
            except type(self).DoesNotExist:
                pass  # Cas rare : suppression concurrente

        if is_new:
            self.clean()

        super().save(*args, **kwargs)

        # Génère un code unique basé sur l'identifiant et le nom
        nom_formatte: str = slugify(self.nom)[:50]
        nouveau_code: str = f"{self.id:03d}_{nom_formatte}"

        if self.code != nouveau_code:
            self.code = nouveau_code
            super().save(update_fields=["code"])

        # Invalidation éventuelle du cache des épreuves publiques
        self._invalider_cache_epreuves_publiques_si_necessaire(anciennement_publique)

    def _invalider_cache_epreuves_publiques_si_necessaire(self, anciennement_publique: bool) -> None:
        """
        Invalide le cache des épreuves publiques si `inscription_externe` a changé.

        Args:
            anciennement_publique (bool): Valeur précédente du champ `inscription_externe`.
        """
        if self.inscription_externe != anciennement_publique:
            cache_key = get_cache_key_liste_epreuves_publiques()
            cache.delete(cache_key)

    def domaines_autorises_str(self) -> str:
        """
        Retourne les domaines autorisés sous forme de chaîne multilignes.
        """
        domaines = InscriptionDomaine.objects.filter(epreuve=self)
        return "\n".join([str(d.domaine) for d in domaines])

    def mettre_a_jour_domaines(self, domaines_str: str) -> None:
        """
        Supprime les anciens domaines et ajoute ceux fournis.

        Args:
            domaines_str (str): Chaîne multilignes contenant les domaines.
        """
        InscriptionDomaine.objects.filter(epreuve=self).delete()
        domaines_set: Set[str] = {
            d.strip() for d in domaines_str.split('\n') if d.strip().startswith('@')
        }
        for domaine in domaines_set:
            InscriptionDomaine.objects.create(epreuve=self, domaine=domaine)

    def ajouter_au_comite(self, user: "User") -> None:
        """
        Ajoute l'utilisateur au comité de cette épreuve (sans vérifier s'il y est déjà).
        """
        MembreComite.objects.create(epreuve=self, membre=user)

    def reordonner_exercices(self, liste_ids: list[str]) -> None:
        """
        Met à jour le champ `numero` des exercices dans l'ordre fourni.

        Args:
            liste_ids (list[str]): Liste des IDs d'exercice dans l'ordre souhaité.
        """
        for index, exercice_id in enumerate(liste_ids, start=1):
            Exercice.objects.filter(id=exercice_id, epreuve=self).update(numero=index)

    class Meta:
        db_table = 'Epreuve'
        unique_together = ['nom', 'referent']
        constraints = [
            CheckConstraint(
                check=Q(
                    Q(date_debut__isnull=True) |
                    Q(date_fin__isnull=True) |
                    Q(date_fin__gte=F('date_debut'))
                ),
                name='date_fin_apres_ou_egale_a_date_debut_si_non_null'
            )
        ]
        indexes = [
            models.Index(fields=['referent']),
        ]


class MembreComite(models.Model):
    epreuve = models.ForeignKey(Epreuve, on_delete=models.CASCADE)
    membre = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        db_table = 'MembreComite'
        unique_together = ['epreuve', 'membre']
        indexes = [
            models.Index(fields=['epreuve', 'membre']),
            models.Index(fields=['membre', 'epreuve']),
        ]