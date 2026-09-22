# Vélo post-croissance — modèles économiques

Réflexion en cours sur des modèles économiques pour la filière du vélo, pensés pour la durabilité plutôt que pour le volume vendu. Point de départ : la crise de surcapacité du secteur (201 faillites en France en 2025, faillite du groupe Accell en août 2026).

## Contenu

- [`docs/referentiel-reparateur-durabilite.md`](docs/referentiel-reparateur-durabilite.md) — Référentiel de compétences et grille de rémunération du **réparateur agent de la durabilité** : missions, nomenclature des pannes (qui paie la main d'œuvre selon le type de panne), niveaux de qualification, certification, grille socle + prime, indicateurs, garde-fous, mise en œuvre.
- [`docs/simulation-economique.md`](docs/simulation-economique.md) — Simulation Monte-Carlo du fonds commun en location : 32 scénarios critiques, analyse de sensibilité, tarif de référence et recommandations avant pilote. Code dans [`simulation/simulation.py`](simulation/simulation.py) (`uv run simulation/simulation.py`).
- [`docs/acteurs.md`](docs/acteurs.md) — Registre des acteurs à rencontrer (financeurs, juristes, fabricants, ateliers, usagers), avec les questions à leur poser et un tableau de suivi des contacts.

## Cadre général du projet

Le référentiel s'inscrit dans un modèle plus large, encore en discussion :

- Une **SCIC à trois collèges** (usagers, réparateurs, fabricants), sur le modèle Michelin de facturation à l'usage plutôt qu'à l'achat : **le vélo est loué, jamais vendu** — il reste propriété de la SCIC, le client en paie l'usage et le restitue en fin d'engagement.
- Une **cotisation de location en deux parts** : un forfait fixe (structure, réseau, stock de pièces) et une part variable indexée sur le kilométrage (usure).
- Un **label de durabilité** sur les pièces, certifié par un comité technique indépendant, qui conditionne l'accès aux financements mutualisés.
- Un **fonds commun** qui rémunère réparateurs et fabricants selon des résultats mesurés (durée de vie, taux de réparation, km sans panne), pas selon le volume d'actes ou de pièces vendues.

## Statut

Document de travail. Les taux, seuils et montants du référentiel sont illustratifs et doivent être calés sur des données réelles pendant une phase pilote (voir la section « Mise en œuvre » du référentiel).

## Origine

Document rédigé avec Claude (Anthropic) à partir d'une série d'échanges sur les modèles post-croissance et la crise du secteur du vélo.
